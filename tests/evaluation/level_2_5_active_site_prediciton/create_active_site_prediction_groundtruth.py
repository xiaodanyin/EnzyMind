import json
import os
import re
import time
from typing import Dict, List, Optional

import nbformat
import requests


def extract_uniprot_ids_from_notebook(notebook_path: str) -> List[str]:
    """Extract unique test UniProt IDs from the reference notebook."""
    pattern = r"Please predict the catalytic active site of the enzyme\s+([A-Z0-9]+)\."

    with open(notebook_path, "r", encoding="utf-8") as handle:
        notebook = nbformat.read(handle, as_version=4)

    uniprot_ids: List[str] = []
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue

        match = re.search(pattern, cell.source)
        if match:
            uniprot_id = match.group(1)
            if uniprot_id not in uniprot_ids:
                uniprot_ids.append(uniprot_id)

    return uniprot_ids


def extract_site_entry(feature: Dict) -> Dict:
    location = feature.get("location", {})
    start = location.get("start", {}).get("value")
    end = location.get("end", {}).get("value")
    return {
        "start": start,
        "end": end,
    }


def extract_active_and_binding_sites(payload: Dict) -> Dict[str, List[Dict]]:
    active_sites: List[Dict] = []
    binding_sites: List[Dict] = []

    for feature in payload.get("features", []):
        feature_type = feature.get("type")
        if feature_type == "Active site":
            active_sites.append(extract_site_entry(feature))
        elif feature_type == "Binding site":
            binding_sites.append(extract_site_entry(feature))

    return {
        "active_sites": active_sites,
        "binding_sites": binding_sites,
    }


def fetch_uniprot_active_sites(uniprot_id: str) -> Optional[Dict]:
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    try:
        print(f"🔍 Fetching {uniprot_id}...", end=" ")
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print(f"✗ HTTP {response.status_code}")
            return None

        payload = response.json()
        site_data = extract_active_and_binding_sites(payload)
        active_count = len(site_data["active_sites"])
        binding_count = len(site_data["binding_sites"])
        print(f"✓ (active: {active_count}, binding: {binding_count})")

        return {
            "has_site_annotations": bool(active_count or binding_count),
            "active_sites": site_data["active_sites"],
            "binding_sites": site_data["binding_sites"],
        }
    except requests.exceptions.Timeout:
        print("✗ Timeout")
        return None
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return None


def create_ground_truth(notebook_path: str, output_json: str, delay: float = 0.5) -> Dict:
    print("=" * 60)
    print("Creating Ground Truth JSON for Level 2.5 Active Site Prediction")
    print("=" * 60)

    print(f"\n📖 Reading UniProt IDs from: {notebook_path}")
    uniprot_ids = extract_uniprot_ids_from_notebook(notebook_path)
    print(f"✓ Found {len(uniprot_ids)} UniProt IDs")

    ground_truth = {}
    for index, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{index}/{len(uniprot_ids)}] ", end="")
        info = fetch_uniprot_active_sites(uniprot_id)

        if info is None:
            ground_truth[uniprot_id] = {
                "has_site_annotations": False,
                "active_sites": [],
                "binding_sites": [],
            }
        else:
            ground_truth[uniprot_id] = info

        if index < len(uniprot_ids):
            time.sleep(delay)

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    print(f"\n💾 Saving ground truth to: {output_json}")
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print("\n✅ Ground truth created successfully")
    print(f"  Total entries: {len(uniprot_ids)}")
    return ground_truth


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    notebook_path = os.path.join(script_dir, "../../enzymind_test_level_2_5_active_site_prediciton.ipynb")
    output_file = os.path.join(script_dir, "files/active_site_prediction_ground_truth.json")

    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    create_ground_truth(notebook_path, output_file, delay=0.5)