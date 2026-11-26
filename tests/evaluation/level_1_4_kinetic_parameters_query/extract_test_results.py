"""
Quick script to extract kinetic parameters query results from notebook.
"""

from data_extractor import DataExtractor


def extract_from_notebook():
    """Extract results from level_1_4 test notebook."""
    print("🔍 Starting to extract kinetic parameters query results from notebook...")

    extractor = DataExtractor()
    notebook_path = "../../gpt_5_2_test_level_1_4_kinetic_parameters_query.ipynb"
    output_path = "./files/extracted_gpt_5_2_results.json"

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