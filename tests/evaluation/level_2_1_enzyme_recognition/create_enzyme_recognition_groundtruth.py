import json
import os


def create_ground_truth_from_test_file(test_file_path: str, output_file: str) -> dict:
    """Create enzyme recognition ground truth from the tab-separated source file."""
    print("Reading test file...")

    ground_truth = {}

    total_entries = 0
    enzyme_count = 0
    non_enzyme_count = 0

    with open(test_file_path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 3:
                raise ValueError(
                    f"Invalid format at line {line_number}: expected 3 tab-separated fields, got {len(parts)}"
                )

            _, label_text, sequence = parts[0], parts[1], parts[2]
            is_enzyme = int(label_text) == 1
            fasta_file = f"{total_entries + 1}.fasta"

            ground_truth[fasta_file] = {
                "is_enzyme": is_enzyme,
                "sequence": sequence,
            }

            total_entries += 1
            if is_enzyme:
                enzyme_count += 1
            else:
                non_enzyme_count += 1

    print(f"Saving ground truth to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print("Ground truth created successfully")
    print(f"  Total entries: {total_entries}")
    print(f"  Enzymes: {enzyme_count}")
    print(f"  Non-enzymes: {non_enzyme_count}")
    return ground_truth


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(script_dir, "../../data/enzyme_recognition/enzyme_recognition_test.txt")
    output_file = os.path.join(script_dir, "enzyme_recognition_ground_truth.json")

    if not os.path.exists(test_file):
        raise FileNotFoundError(f"Test file not found: {test_file}")

    create_ground_truth_from_test_file(test_file, output_file)