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
    predicted_is_substrate: Optional[bool] = None


@dataclass
class GroundTruth:
    """Ground truth for one FASTA sample."""

    fasta_file: str
    substrate: str
    is_substrate: bool
    sequence: Optional[str] = None


class SubstrateDeterminationScoringAgent:
    """LLM-based scoring agent for level_2_4 substrate determination."""

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

You need to evaluate system responses for a binary substrate-determination task.
The task is only:
1) Read the protein sequence provided through a FASTA file.
2) Read the queried compound.
3) Determine whether that compound is a substrate of the enzyme in the FASTA file.

This task does NOT require reaction prediction, EC number prediction, or broad function annotation.
Do not reward extra biochemical explanation unless it affects the final binary substrate/non-substrate conclusion.

Please score the system output according to the following 3-dimensional criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. Input parsing (requirement understanding):
   - 1.0: Correctly understands the input includes both a protein FASTA sequence and a queried compound, and the task is binary substrate determination.
   - 0.5: Basic understanding but with minor confusion or unnecessary extra assumptions.
   - 0.0: Misunderstands the input or the task.

2. Output correctness:
   - 1.0: The final substrate/non-substrate judgment matches the ground truth.
   - 0.5: The answer is hedged, partially inconsistent, or ambiguous, but the main judgment is still basically aligned.
   - 0.0: The answer gives the wrong judgment, or fails to provide a usable binary judgment.

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
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for fasta_file, info in data.items():
            self.ground_truth[fasta_file] = GroundTruth(
                fasta_file=fasta_file,
                substrate=info["substrate"],
                is_substrate=info["is_substrate"],
                sequence=info.get("sequence"),
            )

        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        if result.fasta_file not in self.ground_truth:
            return {
                "fasta_file": result.fasta_file,
                "error": f"Ground truth not found for {result.fasta_file}",
            }

        gt = self.ground_truth[result.fasta_file]
        inferred_prediction = self._infer_predicted_is_substrate(result.response_text)

        prompt = f"""
Please analyze the system raw output directly and score it using the criteria below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

<Task>
Determine whether the compound {gt.substrate} is a substrate of the enzyme stored in {result.fasta_file}.
</Task>

<Ground Truth Answer>
- FASTA file: {gt.fasta_file}
- Compound: {gt.substrate}
- Is substrate: {'Yes' if gt.is_substrate else 'No'}
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
                        "substrate": gt.substrate,
                        "is_substrate": gt.is_substrate,
                        "sequence": gt.sequence,
                    },
                    "predicted": {
                        "is_substrate": inferred_prediction,
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
        print(f"🚀 Starting evaluation of {len(results)} samples...")

        individual_results = []
        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)} - {result.fasta_file}")
            evaluation = self.evaluate_single_result(result)
            individual_results.append(evaluation)

            if "scores" in evaluation:
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

    def _infer_predicted_is_substrate(self, response_text: str) -> Optional[bool]:
        text = response_text.lower()

        negative_patterns = [
            r"not\s+a\s+substrate",
            r"is\s+not\s+a\s+substrate",
            r"isn['’]?t\s+a\s+substrate",
            r"unlikely\s+to\s+be\s+a\s+substrate",
            r"cannot\s+be\s+considered\s+a\s+substrate",
            r"no[,\s].*substrate",
        ]
        for pattern in negative_patterns:
            if re.search(pattern, text):
                return False

        positive_patterns = [
            r"is\s+a\s+substrate",
            r"likely\s+a\s+substrate",
            r"can\s+be\s+a\s+substrate",
            r"appears\s+to\s+be\s+a\s+substrate",
            r"yes[,\s].*substrate",
            r"therefore[,\s].*substrate",
        ]
        for pattern in positive_patterns:
            if re.search(pattern, text):
                return True

        if re.search(r"\byes\b", text) and "substrate" in text:
            return True
        if re.search(r"\bno\b", text) and "substrate" in text:
            return False

        return None