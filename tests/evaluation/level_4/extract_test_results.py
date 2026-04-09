"""
Extract test results from Level 4 test notebooks
"""
import os
import json
import nbformat
import re
from typing import List, Dict, Optional


def extract_fasta_file_from_source(source: str) -> Optional[str]:
    """Extract FASTA file name from code"""
    # Pattern match: fasta_file='./data/level_4/1.fasta'
    pattern = r'fasta_file\s*=\s*[\'"].*?/([^/]+\.fasta)[\'"]'
    match = re.search(pattern, source)
    if match:
        return match.group(1)
    return None


def extract_response_from_cell(cell) -> str:
    """Extract complete response text from cell outputs"""
    response_parts = []
    
    if 'outputs' in cell:
        for output in cell['outputs']:
            if output.get('output_type') == 'stream':
                response_parts.append(output.get('text', ''))
            elif output.get('output_type') == 'display_data':
                data = output.get('data', {})
                if 'text/markdown' in data:
                    response_parts.append(data['text/markdown'])
                elif 'text/plain' in data:
                    response_parts.append(data['text/plain'])
            elif output.get('output_type') == 'execute_result':
                data = output.get('data', {})
                if 'text/markdown' in data:
                    response_parts.append(data['text/markdown'])
                elif 'text/plain' in data:
                    response_parts.append(data['text/plain'])
    
    return '\n'.join(response_parts).strip()


def extract_results_from_notebook(notebook_path: str) -> List[Dict]:
    """Extract test results from notebook"""
    print(f"📖 Parsing notebook: {notebook_path}")
    
    # Read notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    results = []
    
    # Parse each cell
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == 'code':
            # Extract FASTA file name from code
            fasta_file = extract_fasta_file_from_source(cell.source)
            
            if fasta_file:
                # Extract question/prompt from code
                question_match = re.search(r'client\.chat\(["\']([^"\']+)["\']', cell.source)
                question = question_match.group(1) if question_match else "Please predict whether the sequence in this file is an enzyme. If so, further predict its EC numbers."
                
                # Get cell output (answer)
                answer = extract_response_from_cell(cell)
                
                if answer:
                    result = {
                        'fasta_file': fasta_file,
                        'question': question,
                        'answer': answer
                    }
                    results.append(result)
                    print(f"  ✓ Extracted: {fasta_file}")
    
    print(f"✓ Extracted {len(results)} test results")
    return results


def main():
    print("=" * 60)
    print("Extract Level 4 Test Results")
    print("=" * 60)
    print()
    
    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Configuration for different test notebooks
    test_configs = [
        # {
        #     'name': 'EnzyMind',
        #     'notebook': '../../enzymind_test_level_4.ipynb',
        #     'output': 'extracted_enzymind_results.json'
        # },
        # Add more configurations for GPT and DeepSeek later
        # {
        #     'name': 'GPT',
        #     'notebook': '../../gpt_5_2_test_level_4.ipynb',
        #     'output': 'extracted_gpt_5_2_level4_results.json'
        # },
        {
            'name': 'DeepSeek',
            'notebook': '../../deepseek_v32_test_level_4.ipynb',
            'output': 'extracted_deepseek_v32_level4_results.json'
        }
    ]
    
    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"Processing: {config['name']}")
        print(f"{'='*60}\n")
        
        notebook_path = os.path.join(script_dir, config['notebook'])
        output_path = os.path.join(script_dir, config['output'])
        
        # Check if notebook exists
        if not os.path.exists(notebook_path):
            print(f"⚠️  Notebook not found: {notebook_path}")
            print(f"   Skipping {config['name']}...\n")
            continue
        
        # Extract results
        try:
            results = extract_results_from_notebook(notebook_path)
            
            if not results:
                print(f"⚠️  No results found in {config['name']} notebook\n")
                continue
            
            # Save to JSON
            print(f"\n💾 Saving results to {config['output']}...")
            output_data = {
                'test_name': config['name'],
                'notebook_path': config['notebook'],
                'total_results': len(results),
                'results': results
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Saved {len(results)} results")
            print(f"📄 File: {output_path}")
            
            # Print summary
            print(f"\n📊 Summary for {config['name']}:")
            print(f"   - Total test cases: {len(results)}")
            print(f"   - Sample result:")
            if results:
                sample = results[0]
                print(f"     • FASTA: {sample['fasta_file']}")
                print(f"     • Question: {sample['question'][:60]}...")
                print(f"     • Answer length: {len(sample['answer'])} chars")
            
        except Exception as e:
            print(f"❌ Error processing {config['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ Extraction complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
