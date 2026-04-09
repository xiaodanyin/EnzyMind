from gemini_enzyme_check_evaluate_agent import SimpleLLMScoringAgent, TestResult
import json
from datetime import datetime
from pathlib import Path


# 配置类
class EvaluationConfig:
    """Evaluation Configuration"""
    EXTRACTED_RESULTS_FILE = "./extracted_gpt_results.json"
    GROUND_TRUTH_FILE = "./enzyme_check_ground_truth.json"
    CSV_FILE = "./results_gemini-flash-latest/gpt_scores_data.csv"
    FULL_RESULTS_FILE = "./results_gemini-flash-latest/gpt_full_results.json"
    REASONING_FILE = "./results_gemini-flash-latest/gpt_reasoning.txt"

def load_test_results(file_path: str) -> list[TestResult]:
    """Load test results file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        test_results = [
            TestResult(
                uniprot_id=item['uniprot_id'],
                response_text=item['response_text']
            )
            for item in data
        ]
        
        print(f"✓ Successfully loaded {len(test_results)} test results")
        return test_results
        
    except FileNotFoundError:
        raise Exception(f"Test results file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Failed to load test results: {e}")


def display_evaluation_summary(evaluation_results: dict):
    """Display evaluation results summary"""
    metrics = evaluation_results['overall_metrics']
    
    print(f"\n📊 Evaluation Complete!")
    print(f"   Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print(f"   Overall Average Score: {metrics.get('average_score', 0):.3f}/1.0")
    print(f"\n📋 Average Scores by Dimension:")
    print(f"   Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}/1.0")
    print(f"   Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}/1.0")
    print(f"   Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}/1.0")


def display_final_summary(evaluation_results: dict):
    """Display final summary"""
    metrics = evaluation_results['overall_metrics']
    
    print("\n" + "="*50)
    print("📈 Final Evaluation Summary:")
    print(f"   Total Test Samples: {metrics['total_tests']}")
    print(f"   Successfully Evaluated: {metrics['success_count']}")
    print(f"   Success Rate: {metrics.get('success_rate', 0):.1f}%")
    print("\n🎯 Average Scores by Dimension (out of 1.0):")
    print(f"   📖 Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}")
    print(f"   ✅ Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}")
    print(f"   📋 Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}")
    print(f"   🏆 Overall Average Score: {metrics.get('average_score', 0):.3f}")


def main():
    """Main evaluation workflow"""
    print("=== LLM Scoring System - Complete Workflow ===\n")
    
    config = EvaluationConfig()
    
    # Step 1: Initialize LLM Scoring Agent
    print("🤖 Step 1: Initialize LLM Scoring Agent")
    try:
        agent = SimpleLLMScoringAgent()
        print(f"✓ LLM Scoring Agent initialized (model: {agent.model})")
    except RuntimeError as e:
        print(f"❌ Initialization failed: {e}")
        print("💡 Please ensure .env file exists in project root with:")
        print("   GEMINI_API_KEY=your_api_key_here")
        return
    
    # Step 2: Load test results
    print(f"\n📖 Step 2: Load test results")
    try:
        test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
        uniprot_ids = [r.uniprot_id for r in test_results]
        print(f"📋 UniProt IDs: {uniprot_ids[:5]}... (total {len(uniprot_ids)})")
    except Exception as e:
        print(f"❌ {e}")
        return
    
    # Step 3: Load ground truth
    print(f"\n📚 Step 3: Load ground truth")
    try:
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
    except Exception as e:
        print(f"❌ Failed to load ground truth: {e}")
        return
    
    # Step 4: Execute LLM evaluation
    print(f"\n🚀 Step 4: Execute LLM evaluation")
    print("⏰ This may take a few minutes, please be patient...")
    
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        return
    
    # Step 5: Generate detailed report
    print(f"\n📄 Step 5: Generate evaluation report")
    try:
        # agent.generate_report(evaluation_results, config.REPORT_FILE)
        print("✓ Detailed report generated")
        display_final_summary(evaluation_results)
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
        return
    
    # Step 6: Generate additional output files
    print(f"\n🎉 Evaluation workflow completed!")
    print_scores_table(evaluation_results)
    print_detailed_reasoning(evaluation_results)
    save_reasoning_file(evaluation_results, config.REASONING_FILE)
    save_full_results_json(evaluation_results, config.FULL_RESULTS_FILE)
    
    # save_scores_summary(evaluation_results, config.ccccccc)
    save_scores_csv(evaluation_results, config.CSV_FILE)
    
    print(f"\n🎊 All files generated successfully!")
    # print(f"   📄 Detailed Report: {config.REPORT_FILE}")
    # print(f"   📊 Scores Summary: {config.SUMMARY_FILE}")
    print(f"   📈 CSV Data: {config.CSV_FILE}")
    print(f"   📝 Reasoning: {config.REASONING_FILE}")
    print(f"   📁 Full Results: {config.FULL_RESULTS_FILE}")


def save_scores_csv(evaluation_results: dict, output_file: str = "scores_data.csv"):
    """Save scores in CSV format for data analysis"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # CSV header
        f.write("UniProt_ID,Input_Parsing,Output_Correctness,Completeness_Coverage,Total_Score\n")
        
        # 数据行
        valid_results = [r for r in evaluation_results['individual_results'] if 'scores' in r]
        for result in valid_results:
            scores = result['scores']
            f.write(f"{result['uniprot_id']},"
                   f"{scores['input_parsing']:.3f},"
                   f"{scores['output_correctness']:.3f},"
                   f"{scores['completeness_coverage']:.3f},"
                   f"{scores['total_score']:.3f}\n")
        
        # Average scores row
        metrics = evaluation_results['overall_metrics']
        f.write(f"Average,"
               f"{metrics.get('avg_input_parsing', 0):.3f},"
               f"{metrics.get('avg_output_correctness', 0):.3f},"
               f"{metrics.get('avg_completeness_coverage', 0):.3f},"
               f"{metrics.get('average_score', 0):.3f}\n")
    
    print(f"📈 CSV scores data saved: {output_file}")
    return output_file


def print_scores_table(evaluation_results):
    """Print formatted scores table"""
    metrics = evaluation_results['overall_metrics']
    individual_results = evaluation_results['individual_results']
    
    print("\n" + "="*80)
    print("📊 Detailed Scores Table")
    print("="*80)


def print_detailed_reasoning(evaluation_results):
    """Print detailed reasoning for each sample's scores"""
    individual_results = evaluation_results['individual_results']
    valid_results = [r for r in individual_results if 'scores' in r]

    if not valid_results:
        print("\n⚠️ No valid results to show reasoning.")
        return

    print("\n" + "=" * 100)
    print("🔍 Detailed Scoring Reasoning (Agent's Explanation)")
    print("=" * 100)

    import textwrap
    for result in valid_results:
        scores = result['scores']
        uniprot_id = result['uniprot_id']

        print(f"\n🆔 {uniprot_id}")
        print("-" * 100)
        print(f"📊 Scores: Input={scores['input_parsing']:.3f} | Correct={scores['output_correctness']:.3f} | "
              f"Complete={scores['completeness_coverage']:.3f} | Total={scores['total_score']:.3f}")

        print("\n💡 Agent's Reasoning:")
        reasoning = scores.get('reasoning', 'No reasoning provided')
        wrapped = textwrap.fill(reasoning, width=95)
        print(wrapped)

    print("=" * 100)


def save_reasoning_file(evaluation_results: dict, output_file: str):
    """Save detailed reasoning to a text file"""
    individual_results = evaluation_results.get('individual_results', [])
    valid_results = [r for r in individual_results if 'scores' in r]

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Detailed Scoring Reasoning (Agent's Explanation)\n")
        f.write("=" * 100 + "\n\n")

        for result in valid_results:
            scores = result['scores']
            uniprot_id = result['uniprot_id']

            f.write(f"🆔 {uniprot_id}\n")
            f.write("-" * 100 + "\n")
            f.write(f"📊 Scores: Input={scores['input_parsing']:.3f} | Correct={scores['output_correctness']:.3f} | "
                    f"Complete={scores['completeness_coverage']:.3f} | Total={scores['total_score']:.3f}\n\n")
            f.write("💡 Agent's Reasoning:\n")
            f.write(scores.get('reasoning', 'No reasoning provided'))
            f.write("\n\n")

    print(f"📝 Detailed reasoning saved: {output_file}")
    return output_file


def save_full_results_json(evaluation_results: dict, output_file: str):
    """Save full evaluation results as JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=2, ensure_ascii=False)

    print(f"📁 Full results JSON saved: {output_file}")
    return output_file


def save_scores_summary(evaluation_results: dict, output_file: str = "scores_summary.txt"):
    """Save scores summary file"""
    metrics = evaluation_results['overall_metrics']
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Evaluation Results Summary ===\n\n")
        f.write(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Test Samples: {metrics['total_tests']}\n")
        f.write(f"Successfully Evaluated: {metrics['success_count']}\n")
        f.write(f"Success Rate: {metrics.get('success_rate', 0):.1f}%\n\n")
        
        f.write("Average Scores by Dimension (out of 1.0):\n")
        f.write(f"  Input Parsing: {metrics.get('avg_input_parsing', 0):.3f}\n")
        f.write(f"  Output Correctness: {metrics.get('avg_output_correctness', 0):.3f}\n") 
        f.write(f"  Completeness/Coverage: {metrics.get('avg_completeness_coverage', 0):.3f}\n")
        f.write(f"  Overall Average Score: {metrics.get('average_score', 0):.3f}\n\n")
        
        # Add detailed scores for each sample
        f.write("Detailed Scores:\n")
        f.write("-" * 60 + "\n")
        for result in evaluation_results['individual_results']:
            if 'scores' in result:
                scores = result['scores']
                f.write(f"UniProt ID: {result['uniprot_id']}\n")
                f.write(f"  Input Parsing: {scores['input_parsing']:.3f}\n")
                f.write(f"  Output Correctness: {scores['output_correctness']:.3f}\n")
                f.write(f"  Completeness/Coverage: {scores['completeness_coverage']:.3f}\n")
                f.write(f"  Total Score: {scores['total_score']:.3f}\n")
                f.write("-" * 60 + "\n")
    
    print(f"📊 Scores summary saved: {output_file}")
    return output_file


def show_reasoning(uniprot_id: str = None):
    """
    Display detailed reasoning for evaluation scores
    
    Args:
        uniprot_id: Optional. If provided, show reasoning for specific UniProt ID only
    """
    config = EvaluationConfig()
    
    print("🔍 Show Reasoning Mode - Display Agent's Thinking Process\n")
    
    # Check if results file exists
    if not Path(config.FULL_RESULTS_FILE).exists():
        print(f"❌ Results file not found: {config.FULL_RESULTS_FILE}")
        print(f"\n💡 To generate the results file, please run:")
        print(f"   python enzyme_check_run_evaluation.py main")
        print(f"\n📂 Current directory structure:")
        
        # Show available files to help user
        results_dir = Path("./results")
        if results_dir.exists():
            print(f"   ✓ ./results/ directory exists")
            csv_files = list(results_dir.glob("*.csv"))
            json_files = list(results_dir.glob("*.json"))
            if csv_files:
                print(f"   📊 CSV files found: {[f.name for f in csv_files]}")
            if json_files:
                print(f"   📁 JSON files found: {[f.name for f in json_files]}")
            else:
                print(f"   ⚠️  No JSON results file found")
        else:
            print(f"   ❌ ./results/ directory does not exist")
        
        print(f"\n🔄 The evaluation workflow will generate:")
        print(f"   • {config.FULL_RESULTS_FILE}")
        print(f"   • {config.REASONING_FILE}")
        print(f"   • {config.CSV_FILE}")
        return
    
    # Load full results
    try:
            
        with open(config.FULL_RESULTS_FILE, 'r', encoding='utf-8') as f:
            evaluation_results = json.load(f)
            
        print(f"✓ Loaded evaluation results from {config.FULL_RESULTS_FILE}\n")
        
    except Exception as e:
        print(f"❌ Failed to load results: {e}")
        return
    
    # Filter results
    individual_results = evaluation_results.get('individual_results', [])
    valid_results = [r for r in individual_results if 'scores' in r]
    
    if not valid_results:
        print("⚠️ No valid results found")
        return
    
    # Filter by UniProt ID if specified
    if uniprot_id:
        valid_results = [r for r in valid_results if r['uniprot_id'] == uniprot_id]
        if not valid_results:
            print(f"⚠️ No results found for UniProt ID: {uniprot_id}")
            available_ids = [r['uniprot_id'] for r in individual_results if 'scores' in r]
            print(f"📋 Available IDs: {', '.join(available_ids)}")
            return
    
    # Display reasoning
    print("=" * 100)
    print(f"🧠 Agent's Evaluation Reasoning {'for ' + uniprot_id if uniprot_id else f'({len(valid_results)} samples)'}")
    print("=" * 100)
    
    import textwrap
    for idx, result in enumerate(valid_results, 1):
        scores = result['scores']
        uid = result['uniprot_id']
        
        print(f"\n{'='*100}")
        print(f"[{idx}/{len(valid_results)}] 🆔 UniProt ID: {uid}")
        print(f"{'='*100}")
        
        # Scores overview
        print(f"\n📊 Scores Summary:")
        print(f"   • Input Parsing:          {scores['input_parsing']:.3f}/1.0")
        print(f"   • Output Correctness:     {scores['output_correctness']:.3f}/1.0")
        print(f"   • Completeness/Coverage:  {scores['completeness_coverage']:.3f}/1.0")
        print(f"   • Total Score:            {scores['total_score']:.3f}/1.0")
        
        # Detailed reasoning
        print(f"\n💡 Agent's Detailed Reasoning:")
        print("-" * 100)
        reasoning = scores.get('reasoning', 'No reasoning provided')
        
        # Format reasoning with proper wrapping
        wrapped_lines = textwrap.fill(reasoning, width=95, 
                                     initial_indent='   ', 
                                     subsequent_indent='   ')
        print(wrapped_lines)
        
        if idx < len(valid_results):
            print("\n")
    
    print("\n" + "=" * 100)
    
    # Show overall metrics
    metrics = evaluation_results.get('overall_metrics', {})
    if not uniprot_id:
        print(f"\n📈 Overall Metrics:")
        print(f"   • Total Samples:     {metrics.get('total_tests', 0)}")
        print(f"   • Success Rate:      {metrics.get('success_rate', 0):.1f}%")
        print(f"   • Average Score:     {metrics.get('average_score', 0):.3f}/1.0")
        print("=" * 100)
    
    print(f"\n✓ Reasoning display complete!")


def quick_test():
    """Quick test function (using first 3 samples from real data)"""
    print("🧪 Quick Test Mode - Using first 3 samples from real data\n")
    
    config = EvaluationConfig()
    
    # Initialize Agent
    try:
        agent = SimpleLLMScoringAgent()
        print(f"✓ LLM Scoring Agent initialized (model: {agent.model})")
    except RuntimeError as e:
        print(f"⚠️ Please configure .env properly: {e}")
        return
    
    # Load first 3 samples from real data
    try:
        print(f"\n📖 Loading test data (first 3 samples)...")
        all_test_results = load_test_results(config.EXTRACTED_RESULTS_FILE)
        test_results = all_test_results[:3]  # Take first 3 only
        print(f"✓ Test samples: {[r.uniprot_id for r in test_results]}")
        
        print(f"\n📚 Loading ground truth...")
        agent.load_ground_truth_from_file(config.GROUND_TRUTH_FILE)
        
    except Exception as e:
        print(f"❌ Failed to load data: {e}")
        return
    
    # Batch evaluation
    print(f"\n🚀 Starting evaluation...")
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        
        # Display results
        display_evaluation_summary(evaluation_results)
        print_scores_table(evaluation_results)
        display_final_summary(evaluation_results)
        
        # Generate files (generate all files so show_reasoning can work)
        print(f"\n📁 Generating result files:")
        print_detailed_reasoning(evaluation_results)
        save_reasoning_file(evaluation_results, config.REASONING_FILE)
        save_full_results_json(evaluation_results, config.FULL_RESULTS_FILE)
        save_scores_csv(evaluation_results, config.CSV_FILE)
        
        print(f"\n🎉 Quick test completed!")
        print(f"\n💡 You can now view reasoning with:")
        print(f"   python enzyme_check_run_evaluation.py show_reasoning")
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")


if __name__ == "__main__":
    print("Please select run mode:")
    print("1. python enzyme_check_run_evaluation.py main - Complete evaluation workflow")
    print("2. python enzyme_check_run_evaluation.py quick - Quick test (first 3 samples)")
    print("3. python enzyme_check_run_evaluation.py show_reasoning - Show agent's reasoning for all samples")
    print("4. python enzyme_check_run_evaluation.py show_reasoning <UniProt_ID> - Show reasoning for specific sample")
    print("")
    
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "main":
            main()
        elif sys.argv[1] == "quick":
            quick_test()
        elif sys.argv[1] == "show_reasoning":
            if len(sys.argv) > 2:
                show_reasoning(sys.argv[2])
            else:
                show_reasoning()
        else:
            print("Unknown parameter, running default workflow")
            main()
    else:
        main()