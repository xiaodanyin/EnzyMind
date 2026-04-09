"""Extract notebook results for level_2_1 enzyme recognition."""
import os
import json
import nbformat
import re
from typing import Any, Dict, List, Optional


def extract_fasta_file_from_source(source: str) -> Optional[str]:
    """Extract FASTA file name from code"""
    pattern = r'fasta_file\s*=\s*[\'"].*?/([^/]+\.fasta)[\'"]'
    match = re.search(pattern.replace(" ", ""), source)
    if match:
        return match.group(1)
    return None


def normalize_output_text(value: Any) -> str:
    """Normalize notebook output payloads to plain text."""
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def extract_response_from_cell(cell) -> str:
    """Extract complete response text from cell outputs"""
    response_parts = []
    
    if 'outputs' in cell:
        for output in cell['outputs']:
            if output.get('output_type') == 'stream':
                response_parts.append(normalize_output_text(output.get('text', '')))
            elif output.get('output_type') == 'display_data':
                data = output.get('data', {})
                if 'text/markdown' in data:
                    response_parts.append(normalize_output_text(data['text/markdown']))
                elif 'text/plain' in data:
                    response_parts.append(normalize_output_text(data['text/plain']))
            elif output.get('output_type') == 'execute_result':
                data = output.get('data', {})
                if 'text/markdown' in data:
                    response_parts.append(normalize_output_text(data['text/markdown']))
                elif 'text/plain' in data:
                    response_parts.append(normalize_output_text(data['text/plain']))
    
    return '\n'.join(response_parts).strip()


def extract_results_from_notebook(notebook_path: str) -> List[Dict[str, str]]:
    """Extract test results from one notebook."""
    print(f"📖 Parsing notebook: {notebook_path}")
    
    # Read notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    results = []
    
    for cell in nb.cells:
        if cell.cell_type == 'code':
            fasta_file = extract_fasta_file_from_source(cell.source)
            
            if fasta_file:
                answer = extract_response_from_cell(cell)
                
                if answer:
                    result = {
                        'fasta_file': fasta_file,
                        'response_text': answer,
                    }
                    results.append(result)
                    print(f"  ✓ Extracted: {fasta_file}")
    
    print(f"✓ Extracted {len(results)} test results")
    return results


def main():
    print("=" * 60)
    print("Extract Level 2.1 Enzyme Recognition Test Results")
    print("=" * 60)
    print()
    
    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    test_configs = [
        {
            'name': 'EnzyMind',
            'notebook': '../../enzymind_test_level_2_1_enzyme_recognition.ipynb',
            'output': './files/extracted_enzymind_results.json'
        },
        # {
        #     'name': 'GPT-5.2',
        #     'notebook': '../../gpt_5_2_test_level_2_1_enzyme_recognition.ipynb',
        #     'output': './files/extracted_gpt_5_2_results.json'
        # },
        # {
        #     'name': 'DeepSeek',
        #     'notebook': '../../deepseek_v32_test_level_2_1_enzyme_recognition.ipynb',
        #     'output': './files/extracted_deepseek_v32_results.json'
        # }
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
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Saved {len(results)} results")
            print(f"📄 File: {output_path}")
            
            # Print summary
            print(f"\n📊 Summary for {config['name']}:")
            print(f"   - Total test cases: {len(results)}")
            print(f"   - Sample result:")
            if results:
                sample = results[0]
                print(f"     • FASTA: {sample['fasta_file']}")
                print(f"     • Response length: {len(sample['response_text'])} chars")
            
        except Exception as e:
            print(f"❌ Error processing {config['name']}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ Extraction complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
