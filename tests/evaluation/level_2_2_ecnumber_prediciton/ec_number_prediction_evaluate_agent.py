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


@dataclass
class GroundTruth:
    """Ground truth for one FASTA sample."""

    fasta_file: str
    ec_numbers: List[str]
    sequence: Optional[str] = None


class ECNumberPredictionScoringAgent:
    """LLM-based scoring agent for level_2_2 EC-number prediction."""

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

You need to evaluate system responses for an EC-number prediction task.
The task is only:
1) Read the protein sequence provided through a FASTA file.
2) Predict the EC number(s) for the enzyme in that file.

Please score the system output according to the following 3-dimensional criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. Input parsing (requirement understanding):
   - 1.0: Correctly understands the input is a FASTA protein sequence and the task is EC-number prediction.
   - 0.5: Basic understanding but with minor confusion or unnecessary extra assumptions.
   - 0.0: Misunderstands the input or the task.

2. Output correctness:
   - 1.0: Predicted EC number(s) match the ground truth exactly, or for multi-label cases the returned set is equivalent.
   - 0.5: Prediction is partially correct, such as getting one correct EC among multiple, giving a correct higher-level prefix like 3.1.1.- for 3.1.1.31, or mixing correct and incorrect EC numbers.
   - 0.0: Predicted EC numbers are wrong, missing, rejected without justification, or not usable.

3. Completeness/coverage:
   - 1.0: Gives a complete usable EC prediction.
   - 0.5: Gives only partial EC levels, or an overly hedged answer that is still somewhat usable.
   - 0.0: Does not provide a usable EC answer.

Return strictly valid JSON in this format:
{
  "input_parsing": 1.0,
  "output_correctness": 1.0,
  "completeness_coverage": 1.0,
  "total_score": 1.0,
  "reasoning": "Detailed scoring rationale"
}"""

    def load_ground_truth_from_file(self, file_path: str):
        """Load ground truth JSON generated from ec_number_prediction_test.csv."""
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for fasta_file, info in data.items():
            self.ground_truth[fasta_file] = GroundTruth(
                fasta_file=fasta_file,
                ec_numbers=info.get("ec_numbers", []),
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
        inferred_prediction = self._infer_predicted_ec_numbers(result.response_text)

        prompt = f"""
Please analyze the system raw output directly and score it using the criteria below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

<Task>
Predict the EC number(s) for the enzyme stored in {result.fasta_file}.
</Task>

<Ground Truth Answer>
- FASTA file: {gt.fasta_file}
- EC numbers: {', '.join(gt.ec_numbers) if gt.ec_numbers else 'None'}
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
                        "ec_numbers": gt.ec_numbers,
                        "sequence": gt.sequence,
                    },
                    "predicted": {
                        "ec_numbers": inferred_prediction,
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

    def _infer_predicted_ec_numbers(self, response_text: str) -> List[str]:
        pattern = r'(?<!\d)(?:EC[:\s]*)?(\d+\.\d+\.\d+\.(?:\d+|-))(?!\d)'
        matches = re.findall(pattern, response_text, flags=re.IGNORECASE)
        normalized = []
        for item in matches:
            if item not in normalized:
                normalized.append(item)
        return normalized