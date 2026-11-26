"""
Quick script to extract prediction results from notebook
"""
from data_extractor import DataExtractor
import json

def extract_from_notebook():
    """Extract results from test results notebook."""
    
    print("🔍 Starting to extract prediction results from notebook...")
    
    # Initialize data extractor
    extractor = DataExtractor()
    
    # Extract results
    notebook_path = "../gpt_5_2_test_level_1_2_sequence_query.ipynb"
    
    try:
        results = extractor.extract_results_from_notebook(notebook_path)
        
        # Save results
        results_data = []
        for result in results:
            results_data.append({
                "uniprot_id": result.uniprot_id,
                "response_text": result.response_text,
                "predicted_sequence": result.predicted_sequence,
                "predicted_length": result.predicted_length,
                "predicted_molecular_weight": result.predicted_molecular_weight
            })
        
        # Save to JSON file
        with open("./level_1_2_sequence_query/extracted_gpt_results.json", "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully extracted {len(results)} results")
        print("📁 Results saved to: ./level_1_2_sequence_query/extracted_gpt_results.json")
        
        # Display extracted UniProt ID list
        uniprot_ids = [r.uniprot_id for r in results]
        print(f"\n📋 Extracted UniProt IDs:")
        for i, uid in enumerate(uniprot_ids, 1):
            print(f"  {i:2d}. {uid}")
        
        # Display preview of first 3 results
        print(f"\n👀 Preview of first 3 results:")
        for i, result in enumerate(results[:3], 1):
            print(f"\n--- Result {i}: {result.uniprot_id} ---")
            print(f"Response length: {len(result.response_text)} characters")
            if result.predicted_sequence:
                print(f"Sequence length: {result.predicted_length}")
            if result.predicted_molecular_weight:
                print(f"Molecular weight: {result.predicted_molecular_weight} Da")
        
        return results
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return None

if __name__ == "__main__":
    extract_from_notebook()