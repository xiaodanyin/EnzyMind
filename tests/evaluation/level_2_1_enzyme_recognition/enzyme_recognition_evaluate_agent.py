import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class TestResult:
    """Evaluation input extracted from a notebook."""

    fasta_file: str
    response_text: str
    predicted_is_enzyme: Optional[bool] = None


@dataclass
class GroundTruth:
    """Ground truth for one FASTA sample."""

    fasta_file: str
    is_enzyme: bool
    sequence: Optional[str] = None


class EnzymeRecognitionScoringAgent:
    """LLM-based scoring agent for level_2_1 enzyme recognition."""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        load_dotenv()

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set DEEPSEEK_API_KEY in .env or pass it as a parameter")

        base_url = api_url or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.ground_truth: Dict[str, GroundTruth] = {}

        self.evaluation_prompt = """You are a professional bioinformatics evaluation expert.

You need to evaluate system responses for a binary enzyme recognition task.
The task is only:
1) Read the protein sequence provided through a FASTA file.
2) Determine whether the sequence is an enzyme.

This task does NOT require EC number prediction, enzyme name prediction, or function annotation.
Do not reward or penalize the answer for adding extra enzyme annotations unless they affect the binary conclusion.

Please score the system output according to the following 3-dimensional criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. Input parsing (requirement understanding):
   - 1.0: Correctly understands the input is a FASTA protein sequence and the task is binary enzyme recognition.
   - 0.5: Basic understanding but with minor confusion or unnecessary extra assumptions.
   - 0.0: Misunderstands the input or the task.

2. Output correctness:
   - 1.0: The final enzyme/non-enzyme judgment matches the ground truth.
   - 0.5: The answer is hedged, partially inconsistent, or ambiguous, but the main judgment is still basically aligned.
   - 0.0: The answer gives the wrong judgment, or fails to provide a usable judgment.
   Important: This metric is based on the binary enzyme/non-enzyme conclusion only.

3. Completeness/coverage:
   - 1.0: Clearly provides a direct binary conclusion.
   - 0.5: Provides an indirect, weak, or overly hedged conclusion that is still somewhat usable.
   - 0.0: Does not answer the binary question.

Return strictly valid JSON in this format:
{
  "input_parsing": 1.0,
  "output_correctness": 1.0,
  "completeness_coverage": 1.0,
  "total_score": 1.0,
  "reasoning": "Detailed scoring rationale"
}"""

    def load_ground_truth_from_file(self, file_path: str):
        """Load ground truth JSON generated from enzyme_recognition_test.txt."""
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for fasta_file, info in data.items():
            self.ground_truth[fasta_file] = GroundTruth(
                fasta_file=fasta_file,
                is_enzyme=info["is_enzyme"],
                sequence=info.get("sequence"),
            )

        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        """Evaluate one extracted notebook answer."""
        if result.fasta_file not in self.ground_truth:
            return {
                "fasta_file": result.fasta_file,
                "error": f"Ground truth not found for {result.fasta_file}",
            }

        gt = self.ground_truth[result.fasta_file]
        inferred_prediction = self._infer_predicted_is_enzyme(result.response_text)

        prompt = f"""
Please analyze the system raw output directly and score it using the criteria below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

<Task>
Determine whether the protein sequence stored in {result.fasta_file} is an enzyme.
</Task>

<Ground Truth Answer>
- FASTA file: {gt.fasta_file}
- Is enzyme: {'Yes' if gt.is_enzyme else 'No'}
- Sequence: {gt.sequence if gt.sequence else 'Unknown'}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>
"""

        try:
            llm_response = self._call_llm_api(prompt)
            evaluation = self._parse_llm_response(llm_response)
            return {
                "fasta_file": result.fasta_file,
                "scores": evaluation,
                "details": {
                    "ground_truth": {
                        "is_enzyme": gt.is_enzyme,
                        "sequence": gt.sequence,
                    },
                    "predicted": {
                        "is_enzyme": inferred_prediction,
                    },
                    "raw_output": result.response_text,
                    "llm_response": llm_response,
                },
            }
        except Exception as exc:
            return {
                "fasta_file": result.fasta_file,
                "error": f"LLM evaluation failed: {exc}",
            }

    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Evaluate a batch of test results."""
        print(f"🚀 Starting evaluation of {len(results)} samples...")

        individual_results = []
        success_count = 0
        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)} - {result.fasta_file}")
            evaluation = self.evaluate_single_result(result)
            individual_results.append(evaluation)

            if "scores" in evaluation:
                success_count += 1
                print(f"   ✓ Score: {evaluation['scores']['total_score']:.3f}")
            else:
                print(f"   ✗ Failed: {evaluation.get('error', 'Unknown error')}")

        valid_results = [item for item in individual_results if "scores" in item]
        if not valid_results:
            return {
                "overall_metrics": {
                    "total_tests": len(results),
                    "success_count": 0,
                    "error": "No valid evaluation results",
                },
                "individual_results": individual_results,
            }

        avg_input_parsing = sum(item["scores"]["input_parsing"] for item in valid_results) / len(valid_results)
        avg_output_correctness = sum(item["scores"]["output_correctness"] for item in valid_results) / len(valid_results)
        avg_completeness_coverage = sum(item["scores"]["completeness_coverage"] for item in valid_results) / len(valid_results)
        avg_total_score = sum(item["scores"]["total_score"] for item in valid_results) / len(valid_results)

        return {
            "overall_metrics": {
                "total_tests": len(results),
                "success_count": len(valid_results),
                "success_rate": len(valid_results) / len(results) * 100,
                "average_score": avg_total_score,
                "avg_input_parsing": avg_input_parsing,
                "avg_output_correctness": avg_output_correctness,
                "avg_completeness_coverage": avg_completeness_coverage,
            },
            "individual_results": individual_results,
        }

    def generate_report(self, evaluation_result: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """Generate a readable evaluation report."""
        metrics = evaluation_result["overall_metrics"]
        report = f"""
=== Level 2.1 Enzyme Recognition Evaluation Report ===
Scoring method: {self.model}

Overall metrics:
- Test samples: {metrics['total_tests']}
- Evaluation success rate: {metrics.get('success_rate', 0):.1f}%
- Average score: {metrics.get('average_score', 0):.3f}/1.0

Average dimension scores:
- Input parsing: {metrics.get('avg_input_parsing', 0):.3f}
- Output correctness: {metrics.get('avg_output_correctness', 0):.3f}
- Completeness coverage: {metrics.get('avg_completeness_coverage', 0):.3f}

Detailed results:
"""

        for item in evaluation_result["individual_results"]:
            if "scores" not in item:
                report += f"\n- {item['fasta_file']}: {item.get('error', 'Unknown error')}\n"
                continue

            scores = item["scores"]
            gt = item["details"]["ground_truth"]
            predicted = item["details"]["predicted"]
            report += (
                f"\n{'=' * 50}\n"
                f"FASTA: {item['fasta_file']}\n"
                f"Ground truth: {'enzyme' if gt['is_enzyme'] else 'not enzyme'}\n"
                f"Predicted verdict (heuristic): {predicted['is_enzyme']}\n"
                f"Input parsing: {scores['input_parsing']:.3f}\n"
                f"Output correctness: {scores['output_correctness']:.3f}\n"
                f"Completeness coverage: {scores['completeness_coverage']:.3f}\n"
                f"Total score: {scores['total_score']:.3f}\n"
                f"Reasoning: {scores.get('reasoning', '')}\n"
            )

        if output_file:
            with open(output_file, "w", encoding="utf-8") as handle:
                handle.write(report)
            print(f"📄 Report saved to: {output_file}")

        return report

    def _call_llm_api(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional bioinformatics evaluation expert. Return only JSON.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        return response.choices[0].message.content or ""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start == -1 or json_end <= json_start:
                raise ValueError("No valid JSON response found")

            data = json.loads(response[json_start:json_end])
            input_parsing = float(data.get("input_parsing", 0.0))
            output_correctness = float(data.get("output_correctness", 0.0))
            completeness_coverage = float(data.get("completeness_coverage", 0.0))
            total_score = round(
                (input_parsing + output_correctness + completeness_coverage) / 3,
                3,
            )

            return {
                "input_parsing": input_parsing,
                "output_correctness": output_correctness,
                "completeness_coverage": completeness_coverage,
                "total_score": total_score,
                "reasoning": data.get("reasoning", ""),
                "raw_response": response,
            }
        except Exception as exc:
            print(f"⚠️ Failed to parse LLM response: {exc}")
            return {
                "input_parsing": 0.0,
                "output_correctness": 0.0,
                "completeness_coverage": 0.0,
                "total_score": 0.0,
                "reasoning": f"Parsing failed: {exc}",
                "raw_response": response,
            }

    def _infer_predicted_is_enzyme(self, response_text: str) -> Optional[bool]:
        text = response_text.lower()

        negative_patterns = [
            r"not\s+an\s+enzyme",
            r"is\s+not\s+an\s+enzyme",
            r"isn['’]?t\s+an\s+enzyme",
            r"not\s+predicted\s+to\s+be\s+an\s+enzyme",
            r"sequence.*?is\s+not\s+an\s+enzyme",
            r"no\s+[—-]?\s+the sequence.*?not an enzyme",
        ]
        for pattern in negative_patterns:
            if re.search(pattern, text):
                return False

        positive_patterns = [
            r"is\s+an\s+enzyme",
            r"classified\s+as\s+an\s+enzyme",
            r"predicted\s+to\s+be\s+an\s+enzyme",
            r"should\s+be\s+classified\s+as\s+an\s+enzyme",
            r"very\s+likely\s+an\s+enzyme",
            r"yes\s+[—-]?\s+.*enzyme",
        ]
        for pattern in positive_patterns:
            if re.search(pattern, text):
                return True

        return None