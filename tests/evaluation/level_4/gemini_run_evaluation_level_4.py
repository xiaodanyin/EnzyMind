"""
Level 4 Evaluation Script - Enzyme Prediction Task
Evaluates: 1) Is enzyme? 2) If yes, predict EC numbers
"""
import sys
sys.path.append('..')

from gemini_level_4_evaluate_agent import SimpleLLMScoringAgent, TestResult
import json
from datetime import datetime
from pathlib import Path


# 配置类
class EvaluationConfig:
    """Evaluation Configuration"""
    EXTRACTED_RESULTS_FILE = "./extracted_gpt_5_2_level4_results.json"
    GROUND_TRUTH_FILE = "./level_4_ground_truth.json"
    CSV_FILE = "./results_gemini-flash-latest/gpt_5_2_level4_scores_data.csv"
    RESULTS_DIR = "./results_gemini-flash-latest"

def load_test_results(file_path: str) -> list[TestResult]:
    """Load test results file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract results array from JSON
        results_data = data.get('results', data)  # Support both wrapped and unwrapped formats
        
        test_results = [
            TestResult(
                fasta_file=item['fasta_file'],
                response_text=item.get('answer', item.get('response_text', ''))
            )
            for item in results_data
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
    print(f"   Tool Invocation Correctness: {metrics.get('avg_tool_invocation_correctness', 0):.3f}/1.0")
    print(f"   Information Integration: {metrics.get('avg_information_integration', 0):.3f}/1.0")


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
    print(f"   🔧 Tool Invocation Correctness: {metrics.get('avg_tool_invocation_correctness', 0):.3f}")
    print(f"   🔗 Information Integration: {metrics.get('avg_information_integration', 0):.3f}")
    print(f"   🏆 Overall Average Score: {metrics.get('average_score', 0):.3f}")


def main():
    """Main evaluation workflow"""
    print("=== Level 4 LLM Scoring System - Complete Workflow ===")
    print("Task: Enzyme prediction + EC number prediction\n")
    
    config = EvaluationConfig()
    
    # Create results directory
    Path(config.RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    
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
        fasta_files = [r.fasta_file for r in test_results]
        print(f"📋 FASTA Files: {fasta_files[:5]}... (total {len(fasta_files)})")
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
    print(f"\n🚀 Step 4: Execute LLM evaluation (5-dimensional)")
    print("⏰ This may take a few minutes, please be patient...")
    
    try:
        evaluation_results = agent.evaluate_batch_results(test_results)
        display_evaluation_summary(evaluation_results)
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Generate detailed report
    print(f"\n📄 Step 5: Generate evaluation report")
    try:
        report_file = f"{config.RESULTS_DIR}/gpt_5_2_level4_evaluation_report.txt"
        agent.generate_report(evaluation_results, report_file)
        print(f"✓ Detailed report generated: {report_file}")
        display_final_summary(evaluation_results)
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
        return
    
    # Step 6: Generate additional output files
    print(f"\n📊 Step 6: Generate score data files")
    print_scores_table(evaluation_results)
    
    # Print detailed reasoning
    print(f"\n📝 Detailed Scoring Reasoning:")
    print_detailed_reasoning(evaluation_results)
    
    save_scores_csv(evaluation_results, config.CSV_FILE)
    
    # Save full results as JSON
    json_file = f"{config.RESULTS_DIR}/gpt_5_2_level4_full_results.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
    print(f"📁 Full results JSON saved: {json_file}")
    
    print(f"\n🎉 Evaluation workflow completed!")
    print(f"   📄 Detailed Report: {report_file}")
    print(f"   📈 CSV Data: {config.CSV_FILE}")
    print(f"   📁 Full Results: {json_file}")


def save_scores_csv(evaluation_results: dict, output_file: str = "scores_data.csv"):
    """Save scores in CSV format for data analysis"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # CSV header
        f.write("FASTA_File,Input_Parsing,Output_Correctness,Completeness_Coverage,"
                "Tool_Invocation,Info_Integration,Total_Score\n")
        
        # Data rows
        valid_results = [r for r in evaluation_results['individual_results'] if 'scores' in r]
        for result in valid_results:
            scores = result['scores']
            f.write(f"{result['fasta_file']},"
                   f"{scores['input_parsing']:.3f},"
                   f"{scores['output_correctness']:.3f},"
                   f"{scores['completeness_coverage']:.3f},"
                   f"{scores['tool_invocation_correctness']:.3f},"
                   f"{scores['information_integration']:.3f},"
                   f"{scores['total_score']:.3f}\n")
        
        # Average scores row
        metrics = evaluation_results['overall_metrics']
        f.write(f"Average,"
               f"{metrics.get('avg_input_parsing', 0):.3f},"
               f"{metrics.get('avg_output_correctness', 0):.3f},"
               f"{metrics.get('avg_completeness_coverage', 0):.3f},"
               f"{metrics.get('avg_tool_invocation_correctness', 0):.3f},"
               f"{metrics.get('avg_information_integration', 0):.3f},"
               f"{metrics.get('average_score', 0):.3f}\n")
    
    print(f"📈 CSV scores data saved: {output_file}")
    return output_file


def print_scores_table(evaluation_results, show_reasoning=False):
    """Print formatted scores table"""
    metrics = evaluation_results['overall_metrics']
    individual_results = evaluation_results['individual_results']
    
    print("\n" + "="*95)
    print("📊 Detailed Scores Table (5-Dimensional)")
    print("="*95)
    
    # Header
    print(f"{'FASTA':<10} {'Input':<7} {'Correct':<8} {'Complete':<9} {'Tool':<6} {'Info':<6} {'Total':<7}")
    print("-" * 95)
    
    # Data rows
    valid_results = [r for r in individual_results if 'scores' in r]
    for result in valid_results:
        scores = result['scores']
        print(f"{result['fasta_file']:<10} "
              f"{scores['input_parsing']:<7.3f} "
              f"{scores['output_correctness']:<8.3f} "
              f"{scores['completeness_coverage']:<9.3f} "
              f"{scores['tool_invocation_correctness']:<6.3f} "
              f"{scores['information_integration']:<6.3f} "
              f"{scores['total_score']:<7.3f}")
        
        # Show reasoning if requested
        if show_reasoning and scores.get('reasoning'):
            print(f"  💡 Reasoning: {scores['reasoning']}...\n")
    
    # Average row
    print("-" * 95)
    print(f"{'Average':<10} "
          f"{metrics.get('avg_input_parsing', 0):<7.3f} "
          f"{metrics.get('avg_output_correctness', 0):<8.3f} "
          f"{metrics.get('avg_completeness_coverage', 0):<9.3f} "
          f"{metrics.get('avg_tool_invocation_correctness', 0):<6.3f} "
          f"{metrics.get('avg_information_integration', 0):<6.3f} "
          f"{metrics.get('average_score', 0):<7.3f}")
    print("="*95)


def print_detailed_reasoning(evaluation_results):
    """Print detailed reasoning for each sample's scores"""
    individual_results = evaluation_results['individual_results']
    valid_results = [r for r in individual_results if 'scores' in r]
    
    print("\n" + "="*100)
    print("🔍 Detailed Scoring Reasoning (Agent's Explanation)")
    print("="*100)
    
    for result in valid_results:
        scores = result['scores']
        fasta_file = result['fasta_file']
        
        print(f"\n📄 {fasta_file}")
        print("-" * 100)
        print(f"📊 Scores: Input={scores['input_parsing']:.3f} | Correct={scores['output_correctness']:.3f} | "
              f"Complete={scores['completeness_coverage']:.3f} | Tool={scores['tool_invocation_correctness']:.3f} | "
              f"Info={scores['information_integration']:.3f} | Total={scores['total_score']:.3f}")
        print(f"\n💡 Agent's Reasoning:")
        reasoning = scores.get('reasoning', 'No reasoning provided')
        # Wrap long text
        import textwrap
        wrapped = textwrap.fill(reasoning, width=95)
        print(wrapped)
        print()
    
    print("="*100)


def quick_test():
    """Quick test function (using first 3 samples from real data)"""
    print("🧪 Quick Test Mode - Using first 3 samples from real data\n")
    
    config = EvaluationConfig()
    
    # Create results directory
    Path(config.RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    
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
        print(f"✓ Test samples: {[r.fasta_file for r in test_results]}")
        
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
        
        # Show detailed reasoning
        print_detailed_reasoning(evaluation_results)
        
        display_final_summary(evaluation_results)
        
        # Generate files
        print(f"\n📁 Generating score files:")
        save_scores_csv(evaluation_results, f"{config.RESULTS_DIR}/quick_test_scores.csv")
        
        # Save detailed reasoning to file
        reasoning_file = f"{config.RESULTS_DIR}/quick_test_reasoning.txt"
        with open(reasoning_file, 'w', encoding='utf-8') as f:
            valid_results = [r for r in evaluation_results['individual_results'] if 'scores' in r]
            for result in valid_results:
                scores = result['scores']
                f.write(f"\n{'='*100}\n")
                f.write(f"File: {result['fasta_file']}\n")
                f.write(f"{'='*100}\n")
                f.write(f"Scores:\n")
                f.write(f"  Input Parsing: {scores['input_parsing']:.3f}\n")
                f.write(f"  Output Correctness: {scores['output_correctness']:.3f}\n")
                f.write(f"  Completeness/Coverage: {scores['completeness_coverage']:.3f}\n")
                f.write(f"  Tool Invocation Correctness: {scores['tool_invocation_correctness']:.3f}\n")
                f.write(f"  Information Integration: {scores['information_integration']:.3f}\n")
                f.write(f"  Total Score: {scores['total_score']:.3f}\n")
                f.write(f"\nAgent's Reasoning:\n")
                f.write(scores.get('reasoning', 'No reasoning provided'))
                f.write(f"\n\n")
        print(f"📝 Detailed reasoning saved: {reasoning_file}")
        
        # Save full results as JSON
        json_file = f"{config.RESULTS_DIR}/quick_test_full_results.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
        print(f"📁 Full results JSON saved: {json_file}")
        
        print(f"\n🎉 Quick test completed!")
        print(f"\n💡 To view detailed reasoning, run: python show_reasoning.py")
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Please select run mode:")
    print("1. python run_evaluation_level4.py main - Complete evaluation workflow")
    print("2. python run_evaluation_level4.py quick - Quick test (first 3 samples)")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "main":
            main()
        elif sys.argv[1] == "quick":
            quick_test()
        else:
            print("Unknown parameter, running default workflow")
            main()
    else:
        main()
