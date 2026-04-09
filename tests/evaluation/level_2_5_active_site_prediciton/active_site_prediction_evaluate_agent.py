import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class TestResult:
    uniprot_id: str
    response_text: str


@dataclass
class SiteEntry:
    start: Optional[int] = None
    end: Optional[int] = None


@dataclass
class GroundTruth:
    uniprot_id: str
    has_site_annotations: bool
    active_sites: List[SiteEntry] = field(default_factory=list)
    binding_sites: List[SiteEntry] = field(default_factory=list)


class ActiveSitePredictionScoringAgent:
    """LLM-based scoring agent for level_2_5 active-site prediction."""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        load_dotenv()

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set DEEPSEEK_API_KEY in .env or pass it as a parameter")

        base_url = api_url or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.ground_truth: Dict[str, GroundTruth] = {}

        self.evaluation_prompt = """You are a professional bioinformatics evaluation expert for enzyme active-site prediction tasks.

You need to assess the quality of system responses for active-site prediction. The task is: given a UniProt ID, predict the catalytic active site residues of that enzyme.

Please score the system output according to the following 3-dimensional criteria:

1. Input parsing (requirement understanding):
   - 1.0: Correctly recognizes the request is to predict catalytic active site information for the given UniProt ID.
   - 0.5: Basic understanding but with minor misunderstanding.
   - 0.0: Misunderstands the task or answers a different biological question.

2. Output correctness:
   - 1.0: Residue positions or ranges are consistent with ground truth.
   - 0.5: Partially correct, partial residue mistakes.
   - 0.0: Fabricated site annotations, wrong conclusion about annotation availability, or mostly incorrect residue information.

3. Completeness/coverage:
   - 1.0: Covers the main active site and binding-site information from ground truth.
   - 0.5: Covers only part of the site information, or reports one important part but misses another.
   - 0.0: Misses nearly all critical site information.

Return strictly valid JSON in this format:
{
  "input_parsing": 1.0,
  "output_correctness": 0.5,
  "completeness_coverage": 1.0,
  "total_score": 0.833,
  "reasoning": "Detailed scoring rationale"
}"""

    def load_ground_truth_from_file(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for uniprot_id, info in data.items():
            self.ground_truth[uniprot_id] = GroundTruth(
                uniprot_id=uniprot_id,
                has_site_annotations=bool(info.get("has_site_annotations", False)),
                active_sites=[SiteEntry(**entry) for entry in info.get("active_sites", [])],
                binding_sites=[SiteEntry(**entry) for entry in info.get("binding_sites", [])],
            )

        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        if result.uniprot_id not in self.ground_truth:
            return {
                "uniprot_id": result.uniprot_id,
                "error": f"Ground truth not found for {result.uniprot_id}",
            }

        gt = self.ground_truth[result.uniprot_id]
        prompt = self._build_evaluation_prompt(result, gt)

        try:
            llm_response = self._call_llm_api(prompt)
            evaluation = self._parse_llm_response(llm_response)
            return {
                "uniprot_id": result.uniprot_id,
                "scores": evaluation,
                "details": {
                    "ground_truth": self._ground_truth_to_dict(gt),
                    "raw_output": result.response_text,
                    "llm_response": llm_response,
                },
            }
        except Exception as exc:
            return {
                "uniprot_id": result.uniprot_id,
                "error": f"LLM evaluation failed: {exc}",
            }

    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        print(f"🚀 Starting evaluation of {len(results)} samples...")

        individual_results = []
        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)} - {result.uniprot_id}")
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

    def _build_evaluation_prompt(self, result: TestResult, gt: GroundTruth) -> str:
        ground_truth_payload = json.dumps(self._ground_truth_to_dict(gt), ensure_ascii=False, indent=2)
        return f"""
Please first identify the active site and binding site information that appears in the system output, then compare it with the ground truth.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

Task: Predict active site information for UniProt ID {result.uniprot_id}

<Ground Truth Answer>
{ground_truth_payload}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>
"""

    def _ground_truth_to_dict(self, gt: GroundTruth) -> Dict[str, Any]:
        return {
            "uniprot_id": gt.uniprot_id,
            "has_site_annotations": gt.has_site_annotations,
            "active_sites": [self._site_entry_to_dict(entry) for entry in gt.active_sites],
            "binding_sites": [self._site_entry_to_dict(entry) for entry in gt.binding_sites],
        }

    def _site_entry_to_dict(self, entry: SiteEntry) -> Dict[str, Any]:
        return {
            "start": entry.start,
            "end": entry.end,
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
            max_tokens=2000,
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