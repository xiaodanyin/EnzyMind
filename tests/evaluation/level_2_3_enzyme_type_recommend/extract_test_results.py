"""Extract notebook results for level_2_3 enzyme-type recommendation."""

import json
import os
import re
from typing import Any, Dict, List, Optional

import nbformat


def extract_reaction_smiles_from_source(source: str) -> Optional[str]:
    """Extract the queried reaction SMILES from a notebook code cell."""
    pattern = r'client\.chat\(r?[\'\"]Can you recommend an enzyme \(EC number\) that may catalyze this reaction:\s*(.*?)\s*\?[\'\"]\)'
    match = re.search(pattern, source, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def normalize_output_text(value: Any) -> str:
    """Normalize notebook output payloads to plain text."""
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def extract_response_from_cell(cell) -> str:
    """Extract complete response text from a notebook cell."""
    response_parts = []

    if "outputs" in cell:
        for output in cell["outputs"]:
            if output.get("output_type") == "stream":
                response_parts.append(normalize_output_text(output.get("text", "")))
            elif output.get("output_type") == "display_data":
                data = output.get("data", {})
                if "text/markdown" in data:
                    response_parts.append(normalize_output_text(data["text/markdown"]))
                elif "text/plain" in data:
                    response_parts.append(normalize_output_text(data["text/plain"]))
            elif output.get("output_type") == "execute_result":
                data = output.get("data", {})
                if "text/markdown" in data:
                    response_parts.append(normalize_output_text(data["text/markdown"]))
                elif "text/plain" in data:
                    response_parts.append(normalize_output_text(data["text/plain"]))

    return "\n".join(response_parts).strip()


def extract_results_from_notebook(notebook_path: str) -> List[Dict[str, str]]:
    """Extract test results from one notebook."""
    print(f"📖 Parsing notebook: {notebook_path}")

    with open(notebook_path, "r", encoding="utf-8") as handle:
        nb = nbformat.read(handle, as_version=4)

    results = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue

        reaction_smiles = extract_reaction_smiles_from_source(cell.source)
        if not reaction_smiles:
            continue

        answer = extract_response_from_cell(cell)
        if answer:
            results.append(
                {
                    "reaction_smiles": reaction_smiles,
                    "response_text": answer,
                }
            )
            print(f"  ✓ Extracted reaction #{len(results)}")

    print(f"✓ Extracted {len(results)} test results")
    return results


def main():
    print("=" * 60)
    print("Extract Level 2.3 Enzyme-Type Recommendation Test Results")
    print("=" * 60)
    print()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_configs = [
        {
            "name": "EnzyMind",
            "notebook": "../../enzymind_test_level_2_3_enzyme_type_recommend.ipynb",
            "output": "files/extracted_enzymind_results.json",
        },
        {
            "name": "GPT-5.2",
            "notebook": "../../gpt_5_2_test_level_2_3_enzyme_type_recommend.ipynb",
            "output": "files/extracted_gpt_5_2_results.json",
        },
        {
            "name": "DeepSeek",
            "notebook": "../../deepseek_v32_test_level_2_3_enzyme_type_recommend.ipynb",
            "output": "files/extracted_deepseek_v32_results.json",
        },
    ]

    for config in test_configs:
        print(f"\n{'=' * 60}")
        print(f"Processing: {config['name']}")
        print(f"{'=' * 60}\n")

        notebook_path = os.path.join(script_dir, config["notebook"])
        output_path = os.path.join(script_dir, config["output"])
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if not os.path.exists(notebook_path):
            print(f"⚠️  Notebook not found: {notebook_path}")
            print(f"   Skipping {config['name']}...\n")
            continue

        try:
            results = extract_results_from_notebook(notebook_path)
            if not results:
                print(f"⚠️  No results found in {config['name']} notebook\n")
                continue

            print(f"\n💾 Saving results to {config['output']}...")
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(results, handle, indent=2, ensure_ascii=False)

            print(f"✓ Saved {len(results)} results")
            print(f"📄 File: {output_path}")
            print(f"\n📊 Summary for {config['name']}:")
            print(f"   - Total test cases: {len(results)}")
            print("   - Sample result:")
            print(f"     • Reaction length: {len(results[0]['reaction_smiles'])} chars")
            print(f"     • Response length: {len(results[0]['response_text'])} chars")
        except Exception as exc:
            print(f"❌ Error processing {config['name']}: {exc}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("✅ Extraction complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()