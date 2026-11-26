import json
from pathlib import Path

from catalytic_reaction_evaluate_agent import CatalyticReactionLLMScoringAgent, TestResult


class EvaluationConfig:
    """Evaluation configuration."""

    EXTRACTED_RESULTS_FILE = "./files/extracted_gpt_results.json"
    GROUND_TRUTH_FILE = "./files/catalytic_reaction_ground_truth.json"
    CSV_FILE = "./evaluate_results/gpt_scores_data.csv"


def load_test_results(file_path: str) -> list[TestResult]:
    """Load test results file."""
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        test_results = [
            TestResult(
                uniprot_id=item["uniprot_id"],
                response_text=item["response_text"],
            )
            for item in data
        ]

        print(f"✓ Successfully loaded {len(test_results)} test results")
        return test_results
    except FileNotFoundError as exc:
        raise Exception(f"Test results file not found: {file_path}") from exc
    except Exception as exc:
        raise Exception(f"Failed to load test results: {exc}") from exc


def display_evaluation_summary(evaluation_results: dict):
    """Display evaluation results summary."""
    metrics = evaluation_results["overall_metrics"]
    print("\n📊 Evaluation Complete!")
    print(f"   Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print(f"   Overall Average Score: {metrics.get('average_score', 0):.3f}/1.0")
    print("\n📋 Average Scores by Dimension:")
    print(f"   Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}/1.0")
    print(f"   Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}/1.0")
    print(f"   Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}/1.0")


def display_final_summary(evaluation_results: dict):
    """Display final summary."""
    metrics = evaluation_results["overall_metrics"]
    print("\n" + "=" * 50)
    print("📈 Final Evaluation Summary:")
    print(f"   Total Test Samples: {metrics['total_tests']}")
    print(f"   Successfully Evaluated: {metrics['success_count']}")
    print(f"   Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print("\n🎯 Average Scores by Dimension (out of 1.0):")
    print(f"   📖 Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}")
    print(f"   ✅ Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}")
    print(f"   📋 Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}")
    print(f"   🏆 Overall Average Score: {metrics.get('average_score', 0):.3f}")


def save_scores_csv(evaluation_results: dict, output_file: str = "scores_data.csv") -> str:
    """Save scores in CSV format."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("UniProt_ID,Input_Parsing,Output_Correctness,Completeness_Coverage,Total_Score\n")

        valid_results = [item for item in evaluation_results["individual_results"] if "scores" in item]
        for result in valid_results:
            scores = result["scores"]
            handle.write(
                f"{result['uniprot_id']},"
                f"{scores['input_parsing']:.3f},"
                f"{scores['output_correctness']:.3f},"
                f"{scores['completeness_coverage']:.3f},"
                f"{scores['total_score']:.3f}\n"
            )

        metrics = evaluation_results["overall_metrics"]
        handle.write(
            f"Average,"
            f"{metrics.get('avg_input_parsing', 0):.3f},"
            f"{metrics.get('avg_output_correctness', 0):.3f},"
            f"{metrics.get('avg_completeness_coverage', 0):.3f},"
            f"{metrics.get('average_score', 0):.3f}\n"
        )

    print(f"📈 CSV scores data saved: {output_path}")
    return str(output_path)


def print_scores_table(evaluation_results: dict):
    """Print formatted scores table."""
    metrics = evaluation_results["overall_metrics"]
    individual_results = evaluation_results["individual_results"]

    print("\n" + "=" * 80)
    print("📊 Detailed Scores Table")
    print("=" * 80)
    print(f"{'UniProt ID':<12} {'Input':<8} {'Correctness':<12} {'Completeness':<12} {'Total':<8}")
    print("-" * 80)

    valid_results = [item for item in individual_results if "scores" in item]
    for result in valid_results:
        scores = result["scores"]
        print(
            f"{result['uniprot_id']:<12} "
            f"{scores['input_parsing']:<8.3f} "
            f"{scores['output_correctness']:<12.3f} "
            f"{scores['completeness_coverage']:<12.3f} "
            f"{scores['total_score']:<8.3f}"
        )

    print("-" * 80)
    print(
        f"{'Average':<12} "
        f"{metrics.get('avg_input_parsing', 0):<8.3f} "
        f"{metrics.get('avg_output_correctness', 0):<12.3f} "
        f"{metrics.get('avg_completeness_coverage', 0):<12.3f} "
        f"{metrics.get('average_score', 0):<8.3f}"
    )
    print("=" * 80)


def main():
    """Main evaluation workflow."""
    print("=== LLM Scoring System - Catalytic Reaction Query Workflow ===\n")

    config = EvaluationConfig()

    print("🤖 Step 1: Initialize LLM Scoring Agent")
    try:
        agent = CatalyticReactionLLMScoringAgent()
        print(f"✓ LLM Scoring Agent initialized (model: {agent.model})")
    except RuntimeError as exc:
        print(f"❌ Initialization failed: {exc}")
        print("💡 Please ensure .env file exists in project root with DEEPSEEK_API_KEY=your_api_key_here")
        return

    print("\n📖 Step 2: Load test results")
    try:
        test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
        uniprot_ids = [result.uniprot_id for result in test_results]
        print(f"📋 UniProt IDs: {uniprot_ids[:5]}... (total {len(uniprot_ids)})")
    except Exception as exc:
        print(f"❌ {exc}")
        return

    print("\n📚 Step 3: Load ground truth")
    try:
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
    except Exception as exc:
        print(f"❌ Failed to load ground truth: {exc}")
        return

    print("\n🚀 Step 4: Execute LLM evaluation")
    print("⏰ This may take a few minutes, please be patient...")
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
    except Exception as exc:
        print(f"❌ Evaluation failed: {exc}")
        return

    print("\n📄 Step 5: Generate evaluation report")
    try:
        print("✓ Detailed report generated")
        display_final_summary(evaluation_results)
    except Exception as exc:
        print(f"❌ Failed to generate report: {exc}")
        return

    print("\n🎉 Evaluation workflow completed!")
    print_scores_table(evaluation_results)
    save_scores_csv(evaluation_results, config.CSV_FILE)

    print("\n🎊 All files generated successfully!")
    print(f"   📈 CSV Data: {config.CSV_FILE}")


def quick_test():
    """Quick test function using first 3 samples."""
    print("🧪 Quick Test Mode - Using first 3 samples from real data\n")

    config = EvaluationConfig()

    try:
        agent = CatalyticReactionLLMScoringAgent()
        print("✓ LLM Scoring Agent initialized successfully")
    except RuntimeError as exc:
        print(f"⚠️ Please configure .env properly: {exc}")
        return

    try:
        print("\n📖 Loading test data (first 3 samples)...")
        all_test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
        test_results = all_test_results[:3]
        print(f"✓ Test samples: {[result.uniprot_id for result in test_results]}")

        print("\n📚 Loading ground truth...")
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
    except Exception as exc:
        print(f"❌ Failed to load data: {exc}")
        return

    print("\n🚀 Starting evaluation...")
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
        print_scores_table(evaluation_results)
        display_final_summary(evaluation_results)
        save_scores_csv(evaluation_results, "quick_test_scores.csv")
        print("\n🎉 Quick test completed!")
    except Exception as exc:
        print(f"❌ Evaluation failed: {exc}")


if __name__ == "__main__":
    import sys

    print("Please select run mode:")
    print("1. python catalytic_reaction_run_evaluation.py main - Complete evaluation workflow")
    print("2. python catalytic_reaction_run_evaluation.py quick - Quick test (first 3 samples)")

    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        main()