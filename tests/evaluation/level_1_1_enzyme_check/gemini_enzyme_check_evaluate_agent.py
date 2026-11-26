
import json
import nbformat
import re
import os
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

try:
    import google.genai as genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


@dataclass
class TestResult:
    """Test result data structure"""
    uniprot_id: str
    response_text: str
    predicted_is_enzyme: Optional[bool] = None
    predicted_ec_numbers: List[str] = None
    # predicted_enzyme_name: Optional[str] = None
    
    def __post_init__(self):
        if self.predicted_ec_numbers is None:
            self.predicted_ec_numbers = []


@dataclass 
class GroundTruth:
    """Ground truth data structure"""
    uniprot_id: str
    is_enzyme: bool
    ec_numbers: List[str] = None
    # enzyme_name: Optional[str] = None
    
    def __post_init__(self):
        if self.ec_numbers is None:
            self.ec_numbers = []


class SimpleLLMScoringAgent:
    """Simplified LLM scoring agent"""
    
    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        """
        Initialize LLM scoring agent
        
        Args:
            api_key: API key (optional, will read GEMINI_API_KEY from .env)
            api_url: Reserved parameter for backward compatibility, Gemini SDK does not require it
            model: Model name (optional, will read GEMINI_MODEL from .env)
        """
        # Load the Gemini config from tests/.env explicitly to avoid picking up tests/evaluation/.env
        dotenv_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=True)

        if genai is None:
            raise RuntimeError("Missing dependency google-genai. Please install it with: pip install google-genai")
        
        # API configuration - use Gemini settings only
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set GEMINI_API_KEY in .env or pass it as a parameter")

        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-flash-latest"
        if "preview" in self.model.lower():
            print(f"⚠️ Using preview model {self.model}; JSON-format stability may vary between runs")
        self._client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=120000),
        )
        self._generation_config = types.GenerateContentConfig(
            system_instruction="You are a professional bioinformatics evaluation expert. Please strictly follow requirements and return scoring results in JSON format.",
            temperature=0.0,
            max_output_tokens=20000,
            response_mime_type="application/json",
            http_options=types.HttpOptions(timeout=120000),
        )
        self.ground_truth = {}
        
        # Scoring standard prompt
        self.evaluation_prompt = """You are a professional enzyme database query system evaluation expert.

You need to assess the quality of system responses for enzyme detection tasks. The system's task is: determine whether a protein is an enzyme based on UniProt ID.

Please score the system output according to the following scoring criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. **Input parsing (requirement understanding)**:
   - 1.0: Correctly identify input type (UniProt ID) and understand task objectives
   - 0.5: Basic understanding but with minor omissions
   - 0.0: Incorrect understanding or task objective deviation

2. **Output correctness**:
   - 1.0: Key conclusions are factually consistent with ground truth (correct enzyme status, and any provided EC number is correct; missing EC numbers should not be penalized). If the enzyme status is correct, the score MUST be 1.0 when the output either (i) does not provide any EC number, or (ii) provides only correct EC number(s).   
   - 0.5: The enzyme status is correct, but the provided EC number is incorrect.
   - 0.0: All conclusion incorrect or obvious fabrication

   Important: If the enzyme status is correct, the score MUST NOT be 0.0, regardless of how incorrect or unrelated the EC number appears. This metric evaluates factual correctness only, not completeness. 

3. **Completeness/Coverage**:
     Completeness/Coverage is evaluated independently of output correctness.
   - 1.0: Provide complete information (enzyme status, EC numbers)
   - 0.5: Missing some information but main content complete. For example, if it's an enzyme, but the EC number is missing.
   - 0.0: Large amount of missing critical information

Please directly extract and analyze information from the system's original output without relying on preprocessed fields.

Please strictly return results in the following JSON format:
{
  "input_parsing": 1.0,
  "output_correctness": 0.5,
  "completeness_coverage": 1.0,
  "total_score": 0.833,
    "reasoning": "Detailed scoring rationale..."
}"""
    
    def load_ground_truth_from_file(self, file_path: str):
        """Load ground truth from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.ground_truth = {}
        for uniprot_id, info in data.items():
            if uniprot_id == "_metadata":
                continue
            try:
                self.ground_truth[uniprot_id] = GroundTruth(
                    uniprot_id=uniprot_id,
                    is_enzyme=info['is_enzyme'],
                    ec_numbers=info.get('ec_numbers', []),
                    # enzyme_name=info.get('enzyme_name')
                )
            except KeyError as e:
                print(f"⚠️ Ground truth format error, missing field {e} for {uniprot_id}")
        
        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")
    
    def create_ground_truth_template(self, uniprot_ids: List[str], output_file: str):
        """Create ground truth template"""
        template = {}
        for uniprot_id in uniprot_ids:
            template[uniprot_id] = {
                "is_enzyme": None,  # Need to fill true/false manually
                "ec_numbers": [],   # If enzyme, fill in EC number list
                # "enzyme_name": None,  # If enzyme, fill in enzyme name
                "notes": f"Please fill in correct information for {uniprot_id}"
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Ground truth template created: {output_file}")
        print("Please fill in correct answers manually before running evaluation")
        return template
    
    def extract_results_from_notebook(self, notebook_path: str) -> List[TestResult]:
        """Extract test results from notebook"""
        print(f"📖 Parsing notebook: {notebook_path}")
        
        # Read notebook
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        results = []
        
        # Parse each cell
        for i, cell in enumerate(nb.cells):
            if cell.cell_type == 'code':
                # Extract UniProt ID from code
                uniprot_id = self._extract_uniprot_id_from_source(cell.source)
                
                if uniprot_id:
                    # Get cell output
                    response_text = self._extract_response_from_cell(cell)
                    
                    if response_text:
                        # Create test result
                        test_result = TestResult(
                            uniprot_id=uniprot_id,
                            response_text=response_text
                        )
                        
                        # No longer do pre-parsing, keep raw output for LLM processing
                        # self._parse_predictions(test_result)  # Commented out pre-parsing
                        results.append(test_result)
        
        print(f"✓ Extracted {len(results)} test results")
        return results
    
    def _extract_uniprot_id_from_source(self, source: str) -> Optional[str]:
        """Extract UniProt ID from code"""
        # Pattern match: "uniprot ID Q8XPH4"
        pattern = r'uniprot\s+ID\s+([A-Z0-9]+)'
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Fallback pattern: "Q8XPH4 is an enzyme"
        pattern2 = r'([A-Z][0-9][A-Z0-9]{3}[0-9])'
        matches = re.findall(pattern2, source)
        if matches:
            return matches[0]
        
        return None
    
    def _extract_response_from_cell(self, cell) -> str:
        """Extract response text from cell"""
        response_text = ""
        
        if 'outputs' in cell:
            for output in cell['outputs']:
                if output.get('output_type') == 'display_data':
                    data = output.get('data', {})
                    if 'text/markdown' in data:
                        response_text += data['text/markdown']
                    elif 'text/plain' in data:
                        response_text += data['text/plain']
                elif output.get('output_type') == 'stream':
                    response_text += output.get('text', '')
        
        return response_text.strip()
    
    def _build_evaluation_prompt(self, result: TestResult, gt: GroundTruth) -> str:
        prompt = f"""
Please score the result according to the scoring criteria below by directly analyzing and extracting information from the “System Raw Output”, 
and then comparing it against the “Ground Truth Answer.”

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

**Task**: Check whether UniProt ID {result.uniprot_id} is an enzyme

<Ground Truth Answer>
- Is enzyme: {'Yes' if gt.is_enzyme else 'No'}
- EC numbers: {', '.join(gt.ec_numbers) if gt.ec_numbers else 'None'}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>

"""
        return prompt

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        """Evaluate a single result using LLM"""
        if result.uniprot_id not in self.ground_truth:
            return {
                'uniprot_id': result.uniprot_id,
                'error': f'Ground truth not found for {result.uniprot_id}'
            }
        
        gt = self.ground_truth[result.uniprot_id]
        
        try:
            prompt = self._build_evaluation_prompt(result, gt)
            llm_response = self._call_llm_api(prompt)
            evaluation = self._parse_llm_response(llm_response)

            return {
                'uniprot_id': result.uniprot_id,
                'scores': evaluation,
                'details': {
                    'ground_truth': {
                        'is_enzyme': gt.is_enzyme,
                        'ec_numbers': gt.ec_numbers,
                        # 'enzyme_name': gt.enzyme_name
                    },
                    'predicted': {
                        'is_enzyme': result.predicted_is_enzyme,
                        'ec_numbers': result.predicted_ec_numbers,
                    },
                    'raw_output': result.response_text,
                    'llm_response': llm_response
                }
            }
            
        except Exception as e:
            return {
                'uniprot_id': result.uniprot_id,
                'error': f'LLM evaluation failed: {str(e)}'
            }
    
    def _is_retryable_error(self, e: Exception) -> bool:
        """Check if the error is a transient server error worth retrying"""
        error_type = type(e).__name__
        error_msg = str(e)
        http_code = getattr(e, 'code', None) or getattr(e, 'status_code', None)
        # Retry on 5xx server errors, timeouts, and connection errors
        if http_code and isinstance(http_code, int) and http_code >= 500:
            return True
        if any(kw in error_type for kw in ('ServerError', 'Timeout', 'ConnectError', 'ConnectionError', 'DeadlineExceeded')):
            return True
        if any(kw in error_msg for kw in ('DEADLINE_EXCEEDED', '500', '502', '503', '504')):
            return True
        return False

    def _call_llm_api(self, prompt: str) -> str:
        """Call LLM API with retry for transient server errors"""
        max_retries = 2
        last_exception = None

        for attempt in range(1, max_retries + 2):  # 1 initial + max_retries
            try:
                if attempt > 1:
                    wait = 5 * attempt
                    print(f"      ⏳ 第{attempt}次尝试，等待{wait}秒后重试...")
                    time.sleep(wait)
                else:
                    print(f"      Calling Gemini API with model {self.model}...")
                start_time = time.time()

                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=self._generation_config,
                )

                elapsed = time.time() - start_time

                # -- 打印响应诊断信息 --
                finish_reasons = []
                for candidate in getattr(response, 'candidates', []) or []:
                    fr = getattr(candidate, 'finish_reason', None)
                    finish_reasons.append(str(fr))
                print(f"      Gemini API completed in {elapsed:.2f}s  "
                      f"finish_reason={finish_reasons}")

                parsed = getattr(response, 'parsed', None)
                if parsed is not None:
                    if isinstance(parsed, (dict, list)):
                        return json.dumps(parsed, ensure_ascii=False)
                    return str(parsed)

                response_text = getattr(response, 'text', '') or ""
                if response_text.strip():
                    return response_text

                candidate_text_parts = []
                for candidate in getattr(response, 'candidates', []) or []:
                    content = getattr(candidate, 'content', None)
                    for part in getattr(content, 'parts', []) or []:
                        part_text = getattr(part, 'text', None)
                        if part_text:
                            candidate_text_parts.append(part_text)

                if candidate_text_parts:
                    return "\n".join(candidate_text_parts)

                prompt_feedback = getattr(response, 'prompt_feedback', None)
                print(f"      ❌ 响应无文本内容!")
                print(f"         finish_reasons = {finish_reasons}")
                print(f"         prompt_feedback = {prompt_feedback}")
                print(f"         candidates数量 = {len(getattr(response, 'candidates', []) or [])}")
                raise ValueError(
                    "Gemini returned no text payload. "
                    f"finish_reasons={finish_reasons}, prompt_feedback={prompt_feedback}"
                )

            except Exception as e:
                last_exception = e
                # 区分不同的错误类型并打印详细信息
                error_type = type(e).__name__
                error_msg = str(e)

                http_code = getattr(e, 'code', None) or getattr(e, 'status_code', None)
                grpc_code = getattr(e, 'grpc_status_code', None)

                print(f"      ❌ API调用异常 (attempt {attempt}/{max_retries + 1}):")
                print(f"         异常类型:  {error_type}")
                if http_code:
                    print(f"         HTTP状态码: {http_code}")
                if grpc_code:
                    print(f"         gRPC状态码: {grpc_code}")
                print(f"         错误信息:  {error_msg[:500]}")

                if any(kw in error_type for kw in ('Timeout', 'ConnectError', 'ConnectionError')):
                    print(f"         🔧 诊断: 网络超时或连接失败")
                elif any(kw in error_type for kw in ('PermissionDenied', 'Unauthorized', '401', '403')):
                    print(f"         🔧 诊断: API密钥无效或权限不足")
                elif '429' in error_msg or 'ResourceExhausted' in error_type:
                    print(f"         🔧 诊断: API配额耗尽或请求频率过高(429 Rate Limit)")
                elif '500' in error_msg or '503' in error_msg or '504' in error_msg or 'ServerError' in error_type:
                    print(f"         🔧 诊断: API服务商服务端错误/超时(5xx)")
                elif 'ValueError' in error_type:
                    print(f"         🔧 诊断: API调用成功但返回内容为空")

                # 可重试的错误且未达重试上限 -> 继续
                if self._is_retryable_error(e) and attempt <= max_retries:
                    print(f"         ↗️ 将自动重试...")
                    continue

                # 不可重试或已耗尽重试次数
                raise Exception(f"API call failed: {error_type}: {error_msg}")

        # 正常不会走到这里
        raise Exception(f"API call failed after {max_retries + 1} attempts: {last_exception}")
    
    def _parse_llm_response(self, response: str) -> Dict[str, float]:
        """Parse LLM response"""
        try:
            cleaned_response = response.strip()

            if cleaned_response.startswith("```"):
                cleaned_response = re.sub(r'^```(?:json)?\s*', '', cleaned_response)
                cleaned_response = re.sub(r'\s*```$', '', cleaned_response)

            # Extract JSON section
            json_start = cleaned_response.find('{')
            json_end = cleaned_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = cleaned_response[json_start:json_end]
                data = json.loads(json_str)
                
                return {
                    'input_parsing': float(data.get('input_parsing', 0.0)),
                    'output_correctness': float(data.get('output_correctness', 0.0)),
                    'completeness_coverage': float(data.get('completeness_coverage', 0.0)),
                    'total_score': float(data.get('total_score', 0.0)),
                    'reasoning': data.get('reasoning', ''),
                    'raw_response': response,
                    'parse_error': False
                }
            else:
                raise ValueError("No valid JSON response found")
                
        except Exception as e:
            print(f"⚠️ Failed to parse LLM response: {e}")
            # 打印原始响应内容帮助诊断
            preview = response[:500] if response else '(空响应)'
            print(f"   📋 原始响应内容(前500字符): {preview}")
            if response and len(response) > 500:
                print(f"   ... (共 {len(response)} 字符)")
            return {
                'input_parsing': 0.0,
                'output_correctness': 0.0,
                'completeness_coverage': 0.0,
                'total_score': 0.0,
                'reasoning': f'Parsing failed: {str(e)}',
                'raw_response': response,
                'parse_error': True
            }
    
    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Batch evaluate results"""
        print(f"🚀 Starting evaluation of {len(results)} samples...")
        
        individual_scores = []
        success_count = 0
        
        for i, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {i}/{len(results)} - {result.uniprot_id}")
            
            evaluation = self.evaluate_single_result(result)
            individual_scores.append(evaluation)
            
            if 'scores' in evaluation:
                success_count += 1
                print(f"   ✓ Score: {evaluation['scores']['total_score']:.3f}")
            else:
                print(f"   ✗ Failed: {evaluation.get('error', 'Unknown error')}")
        
        print(f"✅ Evaluation complete! Success: {success_count}/{len(results)}")
        
        # Calculate overall metrics
        valid_scores = [s for s in individual_scores if 'scores' in s]
        
        if not valid_scores:
            return {
                'overall_metrics': {
                    'total_tests': len(results),
                    'success_count': 0,
                    'error': 'No valid evaluation results'
                },
                'individual_results': individual_scores
            }
        
        # Calculate average scores
        avg_input_parsing = sum(s['scores']['input_parsing'] for s in valid_scores) / len(valid_scores)
        avg_output_correctness = sum(s['scores']['output_correctness'] for s in valid_scores) / len(valid_scores)
        avg_completeness_coverage = sum(s['scores']['completeness_coverage'] for s in valid_scores) / len(valid_scores)
        avg_total_score = sum(s['scores']['total_score'] for s in valid_scores) / len(valid_scores)
        
        return {
            'overall_metrics': {
                'total_tests': len(results),
                'success_count': len(valid_scores),
                'success_rate': len(valid_scores) / len(results) * 100,
                'average_score': avg_total_score,
                'avg_input_parsing': avg_input_parsing,
                'avg_output_correctness': avg_output_correctness,
                'avg_completeness_coverage': avg_completeness_coverage
            },
            'individual_results': individual_scores
        }
    
    def generate_report(self, evaluation_result: Dict[str, Any], output_file: str = None) -> str:
        """Generate evaluation report"""
        metrics = evaluation_result['overall_metrics']
        
        report = f"""
=== Enzyme Check LLM Evaluation Report ===
Scoring method: {self.model} Intelligent Scoring
Scoring standard: Input parsing + Output correctness + Completeness/Coverage

📊 Overall Metrics:
- Test samples: {metrics['total_tests']}
- Evaluation success rate: {metrics.get('success_rate', 0):.1f}%
- Comprehensive average score: {metrics.get('average_score', 0):.3f}/1.0

📋 Three-dimensional Evaluation Average Scores:
- Input parsing/requirement understanding: {metrics.get('avg_input_parsing', 0):.3f}
- Output correctness: {metrics.get('avg_output_correctness', 0):.3f}
- Completeness/coverage: {metrics.get('avg_completeness_coverage', 0):.3f}

📝 Detailed Results:
"""
        
        for result in evaluation_result['individual_results']:
            if 'scores' in result:
                scores = result['scores']
                report += f"\n{'='*50}\n"
                report += f"🆔 UniProt ID: {result['uniprot_id']}\n"
                report += f"📊 Comprehensive score: {scores['total_score']:.3f}\n"
                report += f"   • Input parsing: {scores['input_parsing']:.3f}\n"
                report += f"   • Output correctness: {scores['output_correctness']:.3f}\n"
                report += f"   • Completeness coverage: {scores['completeness_coverage']:.3f}\n"
                
                if scores.get('reasoning'):
                    report += f"\n🤖 Scoring rationale: {scores['reasoning'][:200]}...\n"
                
                # Predicted vs Ground truth comparison
                predicted = result['details']['predicted']
                gt = result['details']['ground_truth']
                report += f"\n📈 Result comparison:\n"
                report += f"   Is enzyme: {predicted['is_enzyme']} ← → {gt['is_enzyme']}\n"
                if predicted['ec_numbers'] or gt['ec_numbers']:
                    report += f"   EC numbers: {predicted['ec_numbers']} ← → {gt['ec_numbers']}\n"
            else:
                report += f"\n❌ {result['uniprot_id']}: {result.get('error', 'Unknown error')}\n"
        
        # Performance level
        avg_score = metrics.get('average_score', 0)
        if avg_score >= 0.9:
            grade = "🟢 Excellent"
        elif avg_score >= 0.75:
            grade = "🔵 Good"
        elif avg_score >= 0.5:
            grade = "🟡 Acceptable"
        else:
            grade = "🔴 Needs Improvement"
        
        report += f"\n{'='*50}\n"
        report += f"🏆 Overall rating: {grade}\n"
        report += f"📊 Average score: {avg_score:.3f}/1.0\n"
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📄 Report saved to: {output_file}")
        
        return report


# Usage example
if __name__ == "__main__":
    print("SimpleLLMScoringAgent - Specialized for enzyme check task evaluation")
    print("Please follow the steps in README to use this tool")