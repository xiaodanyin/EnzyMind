import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class TestResult:
    """Evaluation input extracted from a notebook."""

    reaction_smiles: str
    response_text: str


@dataclass
class GroundTruth:
    """Ground truth for one reaction sample."""

    sample_id: str
    reaction_smiles: str
    ec_numbers: List[str]
    ec_level0: str


class EnzymeTypeRecommendScoringAgent:
    """LLM-based scoring agent for level_2_3 enzyme-type recommendation."""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        load_dotenv()

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set DEEPSEEK_API_KEY in .env or pass it as a parameter")

        base_url = api_url or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.ground_truth_by_reaction: Dict[str, GroundTruth] = {}

        self.evaluation_prompt = """You are a professional bioinformatics evaluation expert.

You need to evaluate system responses for an enzyme-type recommendation task.
The task is only:
1) Read the given reaction SMILES.
2) Recommend an enzyme EC number that may catalyze this reaction.

Please score the system output according to the following 3-dimensional criteria:

1. Input parsing (requirement understanding):
   - 1.0: Correctly understands the input is a reaction SMILES and the task is to recommend an enzyme EC number.
   - 0.5: Basic understanding but with minor confusion or unnecessary extra assumptions.
   - 0.0: Misunderstands the input or the task.

2. Output correctness:
   - 1.0: Predicted EC number(s) match the ground truth exactly.
   - 0.5: Prediction is partially correct, such as giving the right top-level or partial EC prefix, or mixing correct and incorrect EC numbers.
   - 0.0: Predicted EC numbers are wrong, missing, or not usable.

3. Completeness/coverage:
   - 1.0: Gives a complete usable EC recommendation.
   - 0.5: Gives only a coarse EC class, partial EC levels, or an overly hedged recommendation that is still somewhat usable.
   - 0.0: Does not provide a usable EC recommendation.

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

        self.ground_truth_by_reaction = {}
        for sample_id, info in data.items():
            reaction_smiles = info["reaction_smiles"]
            self.ground_truth_by_reaction[reaction_smiles] = GroundTruth(
                sample_id=sample_id,
                reaction_smiles=reaction_smiles,
                ec_numbers=info.get("ec_numbers", []),
                ec_level0=str(info.get("ec_level0", "")),
            )

        print(f"✓ Loaded {len(self.ground_truth_by_reaction)} ground truth entries")

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        if result.reaction_smiles not in self.ground_truth_by_reaction:
            return {
                "reaction_smiles": result.reaction_smiles,
                "error": "Ground truth not found for reaction_smiles",
            }

        gt = self.ground_truth_by_reaction[result.reaction_smiles]
        inferred_prediction = self._infer_predicted_ec_numbers(result.response_text)

        prompt = f"""
Please analyze the system raw output directly and score it using the criteria below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

<Task>
Recommend an enzyme EC number that may catalyze the given reaction.
</Task>

<Ground Truth Answer>
- Sample ID: {gt.sample_id}
- Reaction SMILES: {gt.reaction_smiles}
- EC numbers: {', '.join(gt.ec_numbers) if gt.ec_numbers else 'None'}
- EC level 0: {gt.ec_level0 if gt.ec_level0 else 'Unknown'}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>
"""

        try:
            llm_response = self._call_llm_api(prompt)
            evaluation = self._parse_llm_response(llm_response)
            return {
                "sample_id": gt.sample_id,
                "reaction_smiles": result.reaction_smiles,
                "scores": evaluation,
                "details": {
                    "ground_truth": {
                        "ec_numbers": gt.ec_numbers,
                        "ec_level0": gt.ec_level0,
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
                "reaction_smiles": result.reaction_smiles,
                "error": f"LLM evaluation failed: {exc}",
            }

    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        print(f"🚀 Starting evaluation of {len(results)} samples...")

        individual_results = []
        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)}")
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

    def _infer_predicted_ec_numbers(self, response_text: str) -> List[str]:
        pattern = r'(?<!\d)(?:EC[:\s]*)?(\d+\.\d+\.\d+\.(?:\d+|[A-Za-z0-9-]+|-))(?!\d)'
        matches = re.findall(pattern, response_text, flags=re.IGNORECASE)
        normalized = []
        for item in matches:
            if item not in normalized:
                normalized.append(item)
        return normalized