
import json
import nbformat
import re
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv


@dataclass
class TestResult:
    """Test result data structure for Level 4 task"""
    fasta_file: str  # FASTA文件名(如 1.fasta)
    response_text: str  # 系统完整输出
    tool_trace: Optional[str] = None  # 工具调用轨迹
    
    def __post_init__(self):
        pass


@dataclass 
class GroundTruth:
    """Ground truth data structure for Level 4 task"""
    fasta_file: str  # FASTA文件名
    is_enzyme: bool  # 是否是酶
    ec_numbers: Optional[List[str]] = None  # EC编号列表(如果是酶)
    notes: Optional[str] = None  # 备注说明
    
    def __post_init__(self):
        if self.is_enzyme and not self.ec_numbers:
            self.ec_numbers = []


class SimpleLLMScoringAgent:
    """Simplified LLM scoring agent"""
    
    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        """
        Initialize LLM scoring agent
        
        Args:
            api_key: API key (optional, will read DEEPSEEK_API_KEY from .env)
            api_url: API endpoint (optional, will read DEEPSEEK_API_BASE from .env)
            model: Model name (optional, will read DEEPSEEK_MODEL from .env)
        """
        # Load environment variables
        load_dotenv()
        
        # API configuration - prioritize parameters, then env vars, then defaults
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set DEEPSEEK_API_KEY in .env or pass it as a parameter")
            
        base_url = api_url or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        # self.model = "deepseek-reasoner"
        # self.model = "deepseek-chat"
        
        # Initialize OpenAI client
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.ground_truth = {}
        
        # Scoring standard prompt for Level 4 task
        self.evaluation_prompt = """You are a professional enzyme prediction system evaluation expert.

You need to assess the quality of system responses for Level 4 enzyme prediction tasks. The system's task is: 
1) Determine whether the uploaded sequence is an enzyme
2) If yes, predict its EC number(s)
3) If no, clearly state it is not an enzyme

Please score the system output according to the following 5-dimensional scoring criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. **Input parsing (requirement understanding)**:
   - 1.0: Correctly identify input type (sequence/FASTA file) and understand task objectives (enzyme detection + EC prediction), no confusion about target objects
   - 0.5: Basic understanding but with minor omissions or slight misunderstanding of requirements
   - 0.0: Input/intent misunderstood, causing task deviation or object confusion

2. **Output correctness**:
   - 1.0: Both enzyme status and EC number predictions are correct.
   - 0.5: Enzyme status prediction is correct, but EC number prediction is incorrect or partially incorrect.
   - 0.0: Enzyme status prediction is incorrect (regardless of EC prediction)
   The correctness of enzyme status prediction takes precedence. If enzyme status is correct but EC number is wrong, the score MUST be 0.5, not 0.0.
   EC prediction errors, even if they involve completely different EC classes (e.g., hydrolase vs. transferase), MUST still be scored as 0.5 as long as the enzyme status prediction is correct. The severity of EC misclassification MUST NOT change the score to 0.0.

3. **Completeness/Coverage**:
   - 1.0: Covers all required fields/items (enzyme status + EC numbers if applicable)
   - 0.5: Covers partially, missing key items but still usable (e.g., provides only partial EC level such as “EC 3”, “EC 3.1”, “EC 3.1.1” instead of a full four-level EC number)
   - 0.0: Large amount missing, basically didn't answer the question

4. **Tool invocation correctness**:
   - 1.0: Tool-dependent results are produced, indicating that the appropriate tools were successfully invoked, even if the tool usage is not explicitly exposed in the output.
   - 0.5: Partially correct (some tools used correctly but missing key tools)
   - 0.0: Wrong tool selection, no tools used when needed, or tool usage fails to produce results

5. **Information integration**:
   - 1.0: Multi-tool returns + final answer - cross-tool evidence aligned consistently, no conflicts, clear integration
   - 0.5: Some integration but rough/minor conflicts
   - 0.0: Not integrated, confused, conflicts unexplained

Please directly extract and analyze information from the system's original output.

Please strictly return results in the following JSON format:
{
  "input_parsing": 1.0,
  "output_correctness": 0.5,
  "completeness_coverage": 1.0,
  "tool_invocation_correctness": 0.5,
  "information_integration": 1.0,
  "total_score": 0.800,
  "reasoning": "Detailed scoring rationale..."
}"""
    
    def load_ground_truth_from_file(self, file_path: str):
        """Load ground truth from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.ground_truth = {}
        for fasta_file, info in data.items():
            if fasta_file == "_metadata":
                continue
            try:
                self.ground_truth[fasta_file] = GroundTruth(
                    fasta_file=fasta_file,
                    is_enzyme=info['is_enzyme'],
                    ec_numbers=info.get('ec_numbers', None),
                    notes=info.get('notes', None)
                )
            except KeyError as e:
                print(f"⚠️ Ground truth format error, missing field {e} for {fasta_file}")
        
        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")
    
    def create_ground_truth_template(self, fasta_files: List[str], output_file: str):
        """Create ground truth template"""
        template = {}
        for fasta_file in fasta_files:
            template[fasta_file] = {
                "is_enzyme": True,  # Fill in: true if enzyme, false if not
                "ec_numbers": [],   # Fill in: EC numbers list if enzyme, e.g., ["1.1.1.1", "1.1.1.2"]
                "notes": f"Please fill in ground truth for {fasta_file}"
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
                # Extract FASTA file name from code
                fasta_file = self._extract_fasta_file_from_source(cell.source)
                
                if fasta_file:
                    # Get cell output (including tool trace)
                    response_text = self._extract_response_from_cell(cell)
                    
                    if response_text:
                        # Create test result
                        test_result = TestResult(
                            fasta_file=fasta_file,
                            response_text=response_text,
                            tool_trace=self._extract_tool_trace_from_response(response_text)
                        )
                        results.append(test_result)
        
        print(f"✓ Extracted {len(results)} test results")
        return results
    
    def _extract_fasta_file_from_source(self, source: str) -> Optional[str]:
        """Extract FASTA file name from code"""
        # Pattern match: fasta_file='./data/level_4/1.fasta'
        pattern = r'fasta_file\s*=\s*[\'"].*?/([^/]+\.fasta)[\'"]'
        match = re.search(pattern, source)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_tool_trace_from_response(self, response_text: str) -> Optional[str]:
        """Extract tool trace from response if available"""
        # Look for tool invocation patterns in the response
        # This is a placeholder - adjust based on actual response format
        if 'Tool:' in response_text or 'tool' in response_text.lower():
            return response_text  # Return full text for now, LLM will parse
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
    
    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        """Evaluate a single result using LLM"""
        if result.fasta_file not in self.ground_truth:
            return {
                'fasta_file': result.fasta_file,
                'error': f'Ground truth not found for {result.fasta_file}'
            }
        
        gt = self.ground_truth[result.fasta_file]
        
        # Construct evaluation prompt
        prompt = f"""

Please first summarize the Key information found in the "System Raw Output",

then compare it against the "Ground Truth Answer" and score the result according to the <Scoring Criteria> below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

**Task**: Predict whether the sequence in {result.fasta_file} is an enzyme. If so, predict its EC numbers.

<Ground Truth Answer>
- Is Enzyme: {"Yes" if gt.is_enzyme else "No"}
- EC Numbers: {gt.ec_numbers if gt.is_enzyme and gt.ec_numbers else "N/A"}
{f"- Notes: {gt.notes}" if gt.notes else ""}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>


""" 
        try:
            # Call LLM API
            llm_response = self._call_llm_api(prompt)
            
            # Parse response
            evaluation = self._parse_llm_response(llm_response)
            
            return {
                'fasta_file': result.fasta_file,
                'scores': evaluation,
                'details': {
                    'ground_truth': {
                        'is_enzyme': gt.is_enzyme,
                        'ec_numbers': gt.ec_numbers
                    },
                    'raw_output': result.response_text,
                    'tool_trace': result.tool_trace,
                    'llm_response': llm_response
                }
            }
            
        except Exception as e:
            return {
                'fasta_file': result.fasta_file,
                'error': f'LLM evaluation failed: {str(e)}'
            }
    
    def _call_llm_api(self, prompt: str) -> str:
        """Call LLM API"""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional bioinformatics evaluation expert. Please strictly follow requirements and return scoring results in JSON format."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            return response.choices[0].message.content or ""
            
        except Exception as e:
            raise Exception(f"API call failed: {str(e)}")
    
    def _parse_llm_response(self, response: str) -> Dict[str, float]:
        """Parse LLM response"""
        try:
            # Extract JSON section
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                return {
                    'input_parsing': float(data.get('input_parsing', 0.0)),
                    'output_correctness': float(data.get('output_correctness', 0.0)),
                    'completeness_coverage': float(data.get('completeness_coverage', 0.0)),
                    'tool_invocation_correctness': float(data.get('tool_invocation_correctness', 0.0)),
                    'information_integration': float(data.get('information_integration', 0.0)),
                    'total_score': float(data.get('total_score', 0.0)),
                    'reasoning': data.get('reasoning', ''),
                    'raw_response': response
                }
            else:
                raise ValueError("No valid JSON response found")
                
        except Exception as e:
            print(f"⚠️ Failed to parse LLM response: {e}")
            # Return default scores
            return {
                'input_parsing': 0.0,
                'output_correctness': 0.0,
                'completeness_coverage': 0.0,
                'tool_invocation_correctness': 0.0,
                'information_integration': 0.0,
                'total_score': 0.0,
                'reasoning': f'Parsing failed: {str(e)}',
                'raw_response': response
            }
    
    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Batch evaluate results"""
        print(f"🚀 Starting evaluation of {len(results)} samples...")
        
        individual_scores = []
        success_count = 0
        
        for i, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {i}/{len(results)} - {result.fasta_file}")
            
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
        
        # Calculate average scores for all 5 dimensions
        avg_input_parsing = sum(s['scores']['input_parsing'] for s in valid_scores) / len(valid_scores)
        avg_output_correctness = sum(s['scores']['output_correctness'] for s in valid_scores) / len(valid_scores)
        avg_completeness_coverage = sum(s['scores']['completeness_coverage'] for s in valid_scores) / len(valid_scores)
        avg_tool_invocation = sum(s['scores']['tool_invocation_correctness'] for s in valid_scores) / len(valid_scores)
        avg_information_integration = sum(s['scores']['information_integration'] for s in valid_scores) / len(valid_scores)
        avg_total_score = sum(s['scores']['total_score'] for s in valid_scores) / len(valid_scores)
        
        return {
            'overall_metrics': {
                'total_tests': len(results),
                'success_count': len(valid_scores),
                'success_rate': len(valid_scores) / len(results) * 100,
                'average_score': avg_total_score,
                'avg_input_parsing': avg_input_parsing,
                'avg_output_correctness': avg_output_correctness,
                'avg_completeness_coverage': avg_completeness_coverage,
                'avg_tool_invocation_correctness': avg_tool_invocation,
                'avg_information_integration': avg_information_integration
            },
            'individual_results': individual_scores
        }
    
    def generate_report(self, evaluation_result: Dict[str, Any], output_file: str = None) -> str:
        """Generate evaluation report"""
        metrics = evaluation_result['overall_metrics']
        
        report = f"""
=== Level 4 Enzyme Prediction LLM Evaluation Report ===
Scoring method: {self.model} Intelligent Scoring
Scoring standard: 5-Dimensional Evaluation (Input parsing + Output correctness + Completeness/Coverage + Tool invocation correctness + Information integration)

📊 Overall Metrics:
- Test samples: {metrics['total_tests']}
- Evaluation success rate: {metrics.get('success_rate', 0):.1f}%
- Comprehensive average score: {metrics.get('average_score', 0):.3f}/1.0

📋 Five-Dimensional Evaluation Average Scores:
- Input parsing/requirement understanding: {metrics.get('avg_input_parsing', 0):.3f}
- Output correctness: {metrics.get('avg_output_correctness', 0):.3f}
- Completeness/coverage: {metrics.get('avg_completeness_coverage', 0):.3f}
- Tool invocation correctness: {metrics.get('avg_tool_invocation_correctness', 0):.3f}
- Information integration: {metrics.get('avg_information_integration', 0):.3f}

📝 Detailed Results:
"""
        
        for result in evaluation_result['individual_results']:
            if 'scores' in result:
                scores = result['scores']
                report += f"\n{'='*50}\n"
                report += f"🆔 FASTA File: {result['fasta_file']}\n"
                report += f"📊 Comprehensive score: {scores['total_score']:.3f}\n"
                report += f"   • Input parsing: {scores['input_parsing']:.3f}\n"
                report += f"   • Output correctness: {scores['output_correctness']:.3f}\n"
                report += f"   • Completeness coverage: {scores['completeness_coverage']:.3f}\n"
                report += f"   • Tool invocation correctness: {scores['tool_invocation_correctness']:.3f}\n"
                report += f"   • Information integration: {scores['information_integration']:.3f}\n"
                
                if scores.get('reasoning'):
                    report += f"\n🤖 Scoring rationale: {scores['reasoning']}...\n"
                
                # Ground truth comparison
                gt = result['details']['ground_truth']
                report += f"\n📈 Ground Truth:\n"
                report += f"   Is Enzyme: {gt['is_enzyme']}\n"
                if gt['is_enzyme'] and gt['ec_numbers']:
                    report += f"   EC Numbers: {', '.join(gt['ec_numbers'])}\n"
            else:
                report += f"\n❌ {result['fasta_file']}: {result.get('error', 'Unknown error')}\n"
        
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
    print("SimpleLLMScoringAgent - Specialized for Level 4 Enzyme Prediction Task Evaluation")
    print("Task: Predict whether the sequence is an enzyme. If so, predict its EC numbers.")
    print("Evaluation dimensions: 5D (Input parsing + Output correctness + Completeness/Coverage + Tool invocation correctness + Information integration)")
    print("Please follow the steps in README to use this tool")