import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class TestResult:
    """Test result data structure."""

    uniprot_id: str
    response_text: str


@dataclass
class KineticEntry:
    """Single kinetic parameter entry."""

    value: Optional[float] = None
    unit: Optional[str] = None
    substrate: Optional[str] = None


@dataclass
class GroundTruth:
    """Ground truth data structure."""

    uniprot_id: str
    has_kinetics: bool
    km: List[KineticEntry] = field(default_factory=list)
    vmax: List[KineticEntry] = field(default_factory=list)
    kcat_note: Optional[str] = None
    note: Optional[str] = None


class KineticParametersLLMScoringAgent:
    """LLM scoring agent for kinetic parameters query evaluation."""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None):
        load_dotenv()

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("Please set DEEPSEEK_API_KEY in .env or pass it as a parameter")

        base_url = api_url or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.ground_truth: Dict[str, GroundTruth] = {}

        self.evaluation_prompt = """You are a professional bioinformatics evaluation expert for enzyme kinetic-parameter query tasks.

You need to assess the quality of system responses for kinetic parameter queries. The system task is: given a UniProt ID, return curated kinetic parameter information from authoritative sources, especially Km values, Vmax values, and kcat-related notes when available.

Important evaluation rules:
- Some proteins do not have curated kinetic parameters in UniProt.
- If the ground truth indicates no kinetic parameters are available, then a correct response should clearly say that the relevant kinetic parameters were not found or not annotated, and should avoid fabricating values.
- A response does not need to reproduce every wording detail, but it should preserve the main numeric facts, units, and substrate associations when those are available.

Please score the system output according to the following scoring criteria (1.0=completely correct, 0.5=basically correct, 0.0=incorrect):

1. Input parsing (requirement understanding):
   - 1.0: Correctly recognizes the request is about kinetic parameters for the given UniProt ID
   - 0.5: Basic understanding but with minor misunderstanding or extra irrelevant focus
   - 0.0: Misunderstands the task or answers a different biological question

2. Output correctness:
   - 1.0: Correctly reports the presence or absence of kinetic data, and when data exist, the key Km, Vmax, and kcat-related facts are largely consistent with ground truth
   - 0.5: Partially correct but with notable omissions, approximate value issues, unit mistakes, or incomplete substrate/value mapping
   - 0.0: Fabricated values, wrong conclusion about data availability, or mostly incorrect kinetic information

3. Completeness/Coverage:
   - 1.0: Covers the main kinetic information from ground truth, including the major Km entries, Vmax entries, and kcat note when available
   - 0.5: Covers only part of the available kinetic information, or correctly states absence but omits important nuance
   - 0.0: Misses nearly all critical information

Please directly analyze the system's original output without depending on preprocessed fields.

Please strictly return JSON in the following format:
{
  "input_parsing": 1.0,
  "output_correctness": 0.5,
  "completeness_coverage": 1.0,
  "total_score": 0.833,
  "reasoning": "Detailed scoring rationale..."
}"""

    def load_ground_truth_from_file(self, file_path: str):
        """Load ground truth from file."""
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for uniprot_id, info in data.items():
            if uniprot_id == "_metadata":
                continue

            self.ground_truth[uniprot_id] = GroundTruth(
                uniprot_id=uniprot_id,
                has_kinetics=bool(info.get("has_kinetics", False)),
                km=[
                    KineticEntry(
                        value=entry.get("value"),
                        unit=entry.get("unit"),
                        substrate=entry.get("substrate"),
                    )
                    for entry in info.get("km", [])
                ],
                vmax=[
                    KineticEntry(
                        value=entry.get("value"),
                        unit=entry.get("unit"),
                        substrate=entry.get("substrate"),
                    )
                    for entry in info.get("vmax", [])
                ],
                kcat_note=info.get("kcat_note"),
                note=info.get("note"),
            )

        print(f"✓ Loaded {len(self.ground_truth)} ground truth entries")

    def evaluate_single_result(self, result: TestResult) -> Dict[str, Any]:
        """Evaluate a single result using LLM."""
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

    def _build_evaluation_prompt(self, result: TestResult, gt: GroundTruth) -> str:
        """Construct evaluation prompt."""
        ground_truth_payload = json.dumps(self._ground_truth_to_dict(gt), ensure_ascii=False, indent=2)
        return f"""
Please first identify the key kinetic-parameter information that appears in the system output, then compare it with the ground truth.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

Task: Query kinetic parameter information for UniProt ID {result.uniprot_id}

<Ground Truth Answer>
{ground_truth_payload}
</Ground Truth Answer>

<System Raw Output>
{result.response_text}
</System Raw Output>
"""

    def _ground_truth_to_dict(self, gt: GroundTruth) -> Dict[str, Any]:
        """Convert ground truth object to plain dictionary."""
        return {
            "uniprot_id": gt.uniprot_id,
            "has_kinetics": gt.has_kinetics,
            "km": [
                {
                    "value": entry.value,
                    "unit": entry.unit,
                    "substrate": entry.substrate,
                }
                for entry in gt.km
            ],
            "vmax": [
                {
                    "value": entry.value,
                    "unit": entry.unit,
                    "substrate": entry.substrate,
                }
                for entry in gt.vmax
            ],
            "kcat_note": gt.kcat_note,
            "note": gt.note,
        }

    def _call_llm_api(self, prompt: str) -> str:
        """Call LLM API."""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional bioinformatics evaluation expert. Return only the requested scoring JSON.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1,
                max_tokens=7200,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise Exception(f"API call failed: {exc}") from exc

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response."""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start == -1 or json_end <= json_start:
                raise ValueError("No valid JSON response found")

            data = json.loads(response[json_start:json_end])
            return {
                "input_parsing": float(data.get("input_parsing", 0.0)),
                "output_correctness": float(data.get("output_correctness", 0.0)),
                "completeness_coverage": float(data.get("completeness_coverage", 0.0)),
                "total_score": float(data.get("total_score", 0.0)),
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

    def evaluate_batch_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Batch evaluate results."""
        print(f"🚀 Starting evaluation of {len(results)} samples...")

        individual_scores = []
        success_count = 0

        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)} - {result.uniprot_id}")
            evaluation = self.evaluate_single_result(result)
            individual_scores.append(evaluation)

            if "scores" in evaluation:
                success_count += 1
                print(f"   ✓ Score: {evaluation['scores']['total_score']:.3f}")
            else:
                print(f"   ✗ Failed: {evaluation.get('error', 'Unknown error')}")

        print(f"✅ Evaluation complete! Success: {success_count}/{len(results)}")

        valid_scores = [item for item in individual_scores if "scores" in item]
        if not valid_scores:
            return {
                "overall_metrics": {
                    "total_tests": len(results),
                    "success_count": 0,
                    "error": "No valid evaluation results",
                },
                "individual_results": individual_scores,
            }

        avg_input_parsing = sum(item["scores"]["input_parsing"] for item in valid_scores) / len(valid_scores)
        avg_output_correctness = sum(item["scores"]["output_correctness"] for item in valid_scores) / len(valid_scores)
        avg_completeness_coverage = sum(item["scores"]["completeness_coverage"] for item in valid_scores) / len(valid_scores)
        avg_total_score = sum(item["scores"]["total_score"] for item in valid_scores) / len(valid_scores)

        return {
            "overall_metrics": {
                "total_tests": len(results),
                "success_count": len(valid_scores),
                "success_rate": len(valid_scores) / len(results) * 100,
                "average_score": avg_total_score,
                "avg_input_parsing": avg_input_parsing,
                "avg_output_correctness": avg_output_correctness,
                "avg_completeness_coverage": avg_completeness_coverage,
            },
            "individual_results": individual_scores,
        }

    def generate_report(self, evaluation_result: Dict[str, Any], output_file: Optional[str] = None) -> str:
        """Generate evaluation report."""
        metrics = evaluation_result["overall_metrics"]
        report = f"""
=== Kinetic Parameters Query LLM Evaluation Report ===
Scoring method: {self.model} intelligent scoring
Scoring standard: Input parsing + Output correctness + Completeness/Coverage

Overall Metrics:
- Test samples: {metrics['total_tests']}
- Evaluation success rate: {metrics.get('success_rate', 0):.1f}%
- Comprehensive average score: {metrics.get('average_score', 0):.3f}/1.0

Three-dimensional Evaluation Average Scores:
- Input parsing/requirement understanding: {metrics.get('avg_input_parsing', 0):.3f}
- Output correctness: {metrics.get('avg_output_correctness', 0):.3f}
- Completeness/coverage: {metrics.get('avg_completeness_coverage', 0):.3f}

Detailed Results:
"""

        for result in evaluation_result["individual_results"]:
            if "scores" not in result:
                report += f"\n❌ {result['uniprot_id']}: {result.get('error', 'Unknown error')}\n"
                continue

            scores = result["scores"]
            gt = result["details"]["ground_truth"]
            report += f"\n{'=' * 50}\n"
            report += f"UniProt ID: {result['uniprot_id']}\n"
            report += f"Comprehensive score: {scores['total_score']:.3f}\n"
            report += f"  Input parsing: {scores['input_parsing']:.3f}\n"
            report += f"  Output correctness: {scores['output_correctness']:.3f}\n"
            report += f"  Completeness coverage: {scores['completeness_coverage']:.3f}\n"
            report += f"  Ground truth has kinetics: {'Yes' if gt['has_kinetics'] else 'No'}\n"
            report += f"  Ground truth Km count: {len(gt['km'])}\n"
            report += f"  Ground truth Vmax count: {len(gt['vmax'])}\n"
            report += f"  Ground truth has kcat note: {'Yes' if gt['kcat_note'] else 'No'}\n"
            if scores.get("reasoning"):
                report += f"  Scoring rationale: {scores['reasoning'][:300]}...\n"

        if output_file:
            with open(output_file, "w", encoding="utf-8") as handle:
                handle.write(report)
            print(f"📄 Report saved to: {output_file}")

        return report


if __name__ == "__main__":
    print("KineticParametersLLMScoringAgent - Specialized for kinetic parameters query evaluation")