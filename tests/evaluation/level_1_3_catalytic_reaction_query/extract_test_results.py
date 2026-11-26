"""
Quick script to extract catalytic reaction query results from notebook.
"""

import json

from data_extractor import DataExtractor


def extract_from_notebook():
    """Extract results from level_1_3 test notebook."""
    print("🔍 Starting to extract catalytic reaction query results from notebook...")

    extractor = DataExtractor()
    notebook_path = "../../deepseek_v32_test_level_1_3_catalytic_reaction_query.ipynb"
    output_path = "./files/extracted_deepseek_v32_results.json"

    try:
        results = extractor.extract_results_from_notebook(notebook_path)

        extractor.save_results_to_json(results, output_path)

        print(f"✅ Successfully extracted {len(results)} results")
        print(f"📁 Results saved to: {output_path}")

        uniprot_ids = [result.uniprot_id for result in results]
        print("\n📋 Extracted UniProt IDs:")
        for index, uid in enumerate(uniprot_ids, 1):
            print(f"  {index:2d}. {uid}")

        print("\n👀 Preview of first 3 results:")
        for index, result in enumerate(results[:3], 1):
            print(f"\n--- Result {index}: {result.uniprot_id} ---")
            print(f"Response length: {len(result.response_text)} characters")

        return results

    except Exception as exc:
        print(f"❌ Extraction failed: {exc}")
        return None


if __name__ == "__main__":
    extract_from_notebook()