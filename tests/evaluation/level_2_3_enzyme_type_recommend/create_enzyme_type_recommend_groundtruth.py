import csv
import json
import os


def parse_ec_numbers(ec_text: str) -> list[str]:
    """Split EC-number field into a normalized list."""
    if not ec_text:
        return []
    return [item.strip() for item in ec_text.split(";") if item.strip()]


def create_ground_truth_from_csv(csv_file_path: str, output_file: str) -> dict:
    """Create enzyme-type recommendation ground truth from source CSV."""
    print("Reading enzyme-type recommendation CSV...")

    ground_truth = {}
    total_entries = 0

    with open(csv_file_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_entries += 1
            sample_id = str(total_entries)
            reaction_smiles = (row.get("rxn_smiles") or "").strip()
            ec_numbers = parse_ec_numbers((row.get("ec") or "").strip())
            ec_level0 = str(row.get("ec_level0") or "").strip()

            ground_truth[sample_id] = {
                "reaction_smiles": reaction_smiles,
                "ec_numbers": ec_numbers,
                "ec_level0": ec_level0,
            }

    print(f"Saving ground truth to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print("Ground truth created successfully")
    print(f"  Total entries: {total_entries}")
    return ground_truth


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(script_dir, "../../data/enzyme_type_recommend/enzyme_type_recommend_test.csv")
    output_file = os.path.join(script_dir, "files/enzyme_type_recommend_ground_truth.json")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    create_ground_truth_from_csv(csv_file, output_file)