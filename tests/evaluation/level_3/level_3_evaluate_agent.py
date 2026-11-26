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
class CatalyticActivity:
    reaction_name: str = ""
    ec_number: Optional[str] = None
    rhea_id: Optional[str] = None


@dataclass
class KineticEntry:
    value: Optional[str] = None
    unit: Optional[str] = None
    substrate: Optional[str] = None


@dataclass
class SiteEntry:
    start: Optional[int] = None
    end: Optional[int] = None


@dataclass
class GroundTruth:
    uniprot_id: str
    is_enzyme: bool
    ec_numbers: List[str] = field(default_factory=list)
    has_activity: bool = False
    activities: List[CatalyticActivity] = field(default_factory=list)
    has_kinetics: bool = False
    km: List[KineticEntry] = field(default_factory=list)
    vmax: List[KineticEntry] = field(default_factory=list)
    kcat_note: Optional[str] = None
    has_site_annotations: bool = False
    active_sites: List[SiteEntry] = field(default_factory=list)
    binding_sites: List[SiteEntry] = field(default_factory=list)


class Level3ScoringAgent:
    """LLM-based scoring agent for level_3 integrated enzyme annotation task."""

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

You need to assess the quality of system responses for Level 3 enzyme annotation tasks. The system's task is:
1) Determine whether the queried UniProt protein is annotated as an enzyme in public databases.
2) If yes, retrieve EC number(s).
3) Retrieve catalytic reaction information when annotated.
4) Retrieve kinetic parameters when annotated.
5) Retrieve catalytic active-site or binding site information when annotated.

Please score the system output according to the same 5-dimensional scoring criteria:

1. Input parsing (requirement understanding):
   - 1.0: Correctly identifies the input object as the queried UniProt protein and understands the task objectives: enzyme verification plus annotation retrieval.
   - 0.5: Basic understanding but with minor omissions or slight misunderstanding of requirements.
   - 0.0: Input or task intent is misunderstood.

2. Output correctness:
    - 1.0: The core answer is correct. The enzyme status is correctly identified, and all provided annotations (e.g., EC number, catalytic reaction information, kinetic parameters, and catalytic active-site information) are consistent with the ground truth. Missing or unprovided details should not reduce the correctness score, as long as the provided core content is correct and no incorrect core annotation is introduced.
    - 0.5: The enzyme status is correct, but at least one provided core annotation is incorrect, overly inconsistent with the ground truth, or mixes correct and incorrect information.
    - 0.0: The enzyme status is wrong, or the answer contains clearly fabricated core annotations.
    The correctness of enzyme-status judgment takes precedence. Correctness should evaluate whether the provided content is factually correct, not whether it is fully complete. Incompleteness alone should not reduce the score from 1.0 to 0.5 unless the missing information is explicitly required by the task.

3. Completeness/Coverage:
- 1.0: Covers all information explicitly required by the task at the required level of detail. For fields such as catalytic or binding-site annotations, motif- or domain-level descriptions are not sufficient when residue-level identities or positions are required.
- 0.5: Covers only part of the explicitly required information, or provides only a coarse-grained / partial version of a required field (e.g., motif- or domain-level site description without residue-level site annotations when exact site residues are required), but the answer remains at least partially usable.
- 0.0: Misses most of the explicitly required information, or fails to address the main request in a usable way.

Completeness should evaluate whether the answer covers the requested scope at the required granularity, not merely whether the topic is mentioned. If the task requires catalytic-site or binding-site annotations and the answer provides only motif/domain-level statements without the specific residues or positions, completeness should generally be 0.5 rather than 1.0.

4. Tool invocation correctness:
    - 1.0: Tool-dependent or database-dependent results are produced correctly, indicating that the necessary public-database information was properly retrieved and used.
    - 0.5: Partially correct, with some required information retrieved but important retrieval/use apparently missing.
    - 0.0: Wrong or failed retrieval, or the answer appears unsupported/fabricated.

5. Information integration:
    - 1.0: Final answer is internally consistent across enzyme status, EC, reaction, kinetics, and active-site information, with no unexplained conflicts.
    - 0.5: Mostly consistent but with minor conflicts or rough integration.
    - 0.0: Contradictory or poorly integrated.

Please directly extract and analyze information from the system's original output.

Return strictly valid JSON in this format:
{
    "extracted_answer": {
        "enzyme_status": "What the system claims about whether the protein is an enzyme",
        "ec_numbers": ["EC numbers explicitly mentioned by the system"],
        "reactions": ["Catalytic reactions explicitly mentioned by the system"],
        "kinetics": ["Kinetic parameters explicitly mentioned by the system"],
        "active_sites": ["Catalytic active-site information explicitly mentioned by the system"],
        "binding_sites": ["Binding site information explicitly mentioned by the system"],
        "notes": ["Other important claims or caveats from the system output"]
    },
  "input_parsing": 1.0,
  "output_correctness": 1.0,
  "completeness_coverage": 1.0,
  "tool_invocation_correctness": 1.0,
  "information_integration": 1.0,
  "total_score": 1.0,
    "dimension_reasoning": {
        "input_parsing": "Why this dimension received this score",
        "output_correctness": "Why this dimension received this score",
        "completeness_coverage": "Why this dimension received this score",
        "tool_invocation_correctness": "Why this dimension received this score",
        "information_integration": "Why this dimension received this score"
    },
  "reasoning": "Detailed scoring rationale"
}"""

    def load_ground_truth_from_file(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.ground_truth = {}
        for uniprot_id, info in data.items():
            if uniprot_id == "_metadata":
                continue
            if info.get("fetch_failed"):
                continue

            self.ground_truth[uniprot_id] = GroundTruth(
                uniprot_id=uniprot_id,
                is_enzyme=bool(info.get("is_enzyme", False)),
                ec_numbers=info.get("ec_numbers", []),
                has_activity=bool(info.get("has_activity", False)),
                activities=[CatalyticActivity(**entry) for entry in info.get("activities", [])],
                has_kinetics=bool(info.get("has_kinetics", False)),
                km=[KineticEntry(**entry) for entry in info.get("km", [])],
                vmax=[KineticEntry(**entry) for entry in info.get("vmax", [])],
                kcat_note=info.get("kcat_note"),
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
        success_count = 0

        for index, result in enumerate(results, 1):
            print(f"📊 Evaluation progress: {index}/{len(results)} - {result.uniprot_id}")
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
        avg_tool_invocation_correctness = sum(item["scores"]["tool_invocation_correctness"] for item in valid_results) / len(valid_results)
        avg_information_integration = sum(item["scores"]["information_integration"] for item in valid_results) / len(valid_results)
        avg_total_score = sum(item["scores"]["total_score"] for item in valid_results) / len(valid_results)

        return {
            "overall_metrics": {
                "total_tests": len(results),
                "success_count": success_count,
                "success_rate": len(valid_results) / len(results) * 100,
                "average_score": avg_total_score,
                "avg_input_parsing": avg_input_parsing,
                "avg_output_correctness": avg_output_correctness,
                "avg_completeness_coverage": avg_completeness_coverage,
                "avg_tool_invocation_correctness": avg_tool_invocation_correctness,
                "avg_information_integration": avg_information_integration,
            },
            "individual_results": individual_results,
        }

    def _build_evaluation_prompt(self, result: TestResult, gt: GroundTruth) -> str:
        ground_truth_payload = json.dumps(self._ground_truth_to_dict(gt), ensure_ascii=False, indent=2)
        return f"""
Please first summarize the key information found in the system raw output,
then compare it against the ground truth and score the result according to the scoring criteria below.

<Scoring Criteria>
{self.evaluation_prompt}
</Scoring Criteria>

Task: Check whether UniProt ID {result.uniprot_id} is annotated as an enzyme in public databases, and if so retrieve EC number, catalytic reaction, kinetic parameters, and catalytic active-site information.

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
            "is_enzyme": gt.is_enzyme,
            "ec_numbers": gt.ec_numbers,
            "has_activity": gt.has_activity,
            "activities": [
                {
                    "reaction_name": item.reaction_name,
                    "ec_number": item.ec_number,
                    "rhea_id": item.rhea_id,
                }
                for item in gt.activities
            ],
            "has_kinetics": gt.has_kinetics,
            "km": [
                {
                    "value": item.value,
                    "unit": item.unit,
                    "substrate": item.substrate,
                }
                for item in gt.km
            ],
            "vmax": [
                {
                    "value": item.value,
                    "unit": item.unit,
                    "substrate": item.substrate,
                }
                for item in gt.vmax
            ],
            "kcat_note": gt.kcat_note,
            "has_site_annotations": gt.has_site_annotations,
            "active_sites": [{"start": item.start, "end": item.end} for item in gt.active_sites],
            "binding_sites": [{"start": item.start, "end": item.end} for item in gt.binding_sites],
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
            max_tokens=1800,
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
            output_correctness = float(
                data.get(
                    "output_correctness",
                    data.get("enzyme_ec_correctness", 0.0),
                )
            )
            completeness_coverage = float(data.get("completeness_coverage", 0.0))
            tool_invocation_correctness = float(data.get("tool_invocation_correctness", 0.0))
            information_integration = float(data.get("information_integration", 0.0))
            total_score = round(
                (
                    input_parsing
                    + output_correctness
                    + completeness_coverage
                    + tool_invocation_correctness
                    + information_integration
                )
                / 5,
                3,
            )

            return {
                "input_parsing": input_parsing,
                "output_correctness": output_correctness,
                "completeness_coverage": completeness_coverage,
                "tool_invocation_correctness": tool_invocation_correctness,
                "information_integration": information_integration,
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
                "tool_invocation_correctness": 0.0,
                "information_integration": 0.0,
                "total_score": 0.0,
                "reasoning": f"Parsing failed: {exc}",
                "raw_response": response,
            }
