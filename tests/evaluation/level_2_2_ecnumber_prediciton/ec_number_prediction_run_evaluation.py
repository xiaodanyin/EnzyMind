import json
import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from ec_number_prediction_evaluate_agent import ECNumberPredictionScoringAgent, TestResult


class EvaluationConfig:
    """Evaluation configuration for one result set."""

    PRESETS = {
        "enzymind": {
            "extracted_results_file": "./files/extracted_enzymind_results.json",
            "results_dir": "./evaluate_results",
            "file_prefix": "enzymind",
        },
        "deepseek": {
            "extracted_results_file": "./files/extracted_deepseek_v32_results.json",
            "results_dir": "./evaluate_results",
            "file_prefix": "deepseek_v32",
        },
        "gpt": {
            "extracted_results_file": "./files/extracted_gpt_5_2_results.json",
            "results_dir": "./evaluate_results",
            "file_prefix": "gpt_5_2",
        },
    }

    def __init__(self, preset: str = "deepseek"):
        if preset not in self.PRESETS:
            raise ValueError(f"Unknown preset: {preset}. Available presets: {', '.join(self.PRESETS)}")

        selected = self.PRESETS[preset]
        self.preset = preset
        self.GROUND_TRUTH_FILE = "./files/ec_number_prediction_ground_truth.json"
        self.EXTRACTED_RESULTS_FILE = selected["extracted_results_file"]
        self.RESULTS_DIR = selected["results_dir"]
        self.CSV_FILE = f"{self.RESULTS_DIR}/{selected['file_prefix']}_scores.csv"


def load_test_results(file_path: str) -> list[TestResult]:
    """Load extracted notebook results."""
    with open(file_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        results_data = data.get("results", data)
    elif isinstance(data, list):
        results_data = data
    else:
        raise ValueError(f"Unsupported extracted results format: {type(data).__name__}")

    test_results = [
        TestResult(
            fasta_file=item["fasta_file"],
            response_text=item.get("response_text", item.get("answer", "")),
        )
        for item in results_data
    ]
    print(f"✓ Successfully loaded {len(test_results)} test results")
    return test_results


def display_evaluation_summary(evaluation_results: dict):
    metrics = evaluation_results["overall_metrics"]
    print("\n📊 Evaluation Complete!")
    print(f"   Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print(f"   Overall Average Score: {metrics.get('average_score', 0):.3f}/1.0")
    print("\n📋 Average Scores by Dimension:")
    print(f"   Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}/1.0")
    print(f"   Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}/1.0")
    print(f"   Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}/1.0")


def save_scores_csv(evaluation_results: dict, output_file: str):
    with open(output_file, "w", encoding="utf-8") as handle:
        handle.write("FASTA_File,Input_Parsing,Output_Correctness,Completeness_Coverage,Total_Score\n")
        valid_results = [item for item in evaluation_results["individual_results"] if "scores" in item]
        for item in valid_results:
            scores = item["scores"]
            handle.write(
                f"{item['fasta_file']},"
                f"{scores['input_parsing']:.3f},"
                f"{scores['output_correctness']:.3f},"
                f"{scores['completeness_coverage']:.3f},"
                f"{scores['total_score']:.3f}\n"
            )

        metrics = evaluation_results["overall_metrics"]
        handle.write(
            f"Average,{metrics.get('avg_input_parsing', 0):.3f},"
            f"{metrics.get('avg_output_correctness', 0):.3f},"
            f"{metrics.get('avg_completeness_coverage', 0):.3f},"
            f"{metrics.get('average_score', 0):.3f}\n"
        )
    print(f"📈 CSV scores data saved: {output_file}")


def main(preset: str = "deepseek"):
    print("=== Level 2.2 EC-number Prediction Evaluation Workflow ===\n")
    config = EvaluationConfig(preset)

    Path(config.RESULTS_DIR).mkdir(parents=True, exist_ok=True)

    print("🤖 Step 1: Initialize scoring agent")
    try:
        agent = ECNumberPredictionScoringAgent()
        print(f"✓ Scoring agent initialized (model: {agent.model})")
    except RuntimeError as exc:
        print(f"❌ Initialization failed: {exc}")
        print("💡 Please ensure .env contains DEEPSEEK_API_KEY")
        return

    print("\n📖 Step 2: Load extracted test results")
    try:
        test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
    except Exception as exc:
        print(f"❌ Failed to load test results: {exc}")
        return

    print("\n📚 Step 3: Load ground truth")
    try:
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
    except Exception as exc:
        print(f"❌ Failed to load ground truth: {exc}")
        return

    print("\n🚀 Step 4: Execute evaluation")
    print("⏰ This may take a few minutes, please be patient...")
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
    except Exception as exc:
        print(f"❌ Evaluation failed: {exc}")
        return

    print("\n📄 Step 5: Generate output file")
    try:
        save_scores_csv(evaluation_results, config.CSV_FILE)
    except Exception as exc:
        print(f"❌ Failed to generate CSV file: {exc}")
        return

    print("\n🎉 Evaluation workflow completed")
    print(f"   📈 CSV: {config.CSV_FILE}")


def quick_test():
    print("🧪 Quick Test Mode - first 3 samples\n")
    config = EvaluationConfig()

    try:
        agent = ECNumberPredictionScoringAgent()
        print(f"✓ Scoring agent initialized (model: {agent.model})")
        all_test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
        test_results = all_test_results[:3]
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
    except Exception as exc:
        print(f"❌ Quick test failed: {exc}")
        return


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        preset = sys.argv[1] if len(sys.argv) > 1 else "enzymind"
        main(preset)