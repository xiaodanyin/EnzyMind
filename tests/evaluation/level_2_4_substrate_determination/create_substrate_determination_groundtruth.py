import csv
import json
import os


def read_fasta_sequence(fasta_path: str) -> str:
    """Read sequence content from a FASTA file."""
    sequence_parts = []
    with open(fasta_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith(">"):
                continue
            sequence_parts.append(line)
    return "".join(sequence_parts)


def create_ground_truth_from_csv(csv_file_path: str, fasta_dir: str, output_file: str) -> dict:
    """Create substrate-determination ground truth from source CSV and FASTA files."""
    print("Reading substrate determination CSV...")

    ground_truth = {}
    total_entries = 0

    with open(csv_file_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_entries += 1
            fasta_file = f"{total_entries}.fasta"
            fasta_path = os.path.join(fasta_dir, fasta_file)
            sequence = read_fasta_sequence(fasta_path) if os.path.exists(fasta_path) else ""

            ground_truth[fasta_file] = {
                "substrate": (row.get("react") or "").strip(),
                "is_substrate": str(row.get("label") or "").strip() == "1",
                "sequence": sequence,
            }

    print(f"Saving ground truth to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print("Ground truth created successfully")
    print(f"  Total entries: {total_entries}")
    return ground_truth


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "../../data/substrate_determination")
    csv_file = os.path.join(data_dir, "substrate_determination_test.csv")
    output_file = os.path.join(script_dir, "files/substrate_determination_ground_truth.json")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    create_ground_truth_from_csv(csv_file, data_dir, output_file)