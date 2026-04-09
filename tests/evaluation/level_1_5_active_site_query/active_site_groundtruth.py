"""
Create ground truth JSON for active site query task.
Fetch curated active site and binding site annotations from UniProt REST API.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests


INPUT_JSON_CANDIDATES = [
    "./files/extracted_enzymind_results.json",
    "./files/extracted_gpt_5_2_results.json",
    "./files/extracted_deepseek_v32_results.json",
]


def resolve_input_json() -> str:
    """Resolve the first available extracted-results file."""
    for candidate in INPUT_JSON_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return INPUT_JSON_CANDIDATES[0]


def normalize_evidence_item(item: Dict) -> str:
    """Normalize evidence entry into a compact string."""
    code = item.get("evidenceCode")
    source = item.get("source")
    identifier = item.get("id")
    parts = [part for part in [code, source, identifier] if part]
    return ":".join(parts) if parts else ""


def extract_site_entry(feature: Dict) -> Dict:
    """Extract a single site entry from UniProt feature payload."""
    location = feature.get("location", {})
    start = location.get("start", {}).get("value")
    end = location.get("end", {}).get("value")
    description = (feature.get("description") or "").strip() or None

    evidences = [normalize_evidence_item(item) for item in feature.get("evidences", [])]
    evidences = [item for item in evidences if item]

    return {
        "start": start,
        "end": end,
        "description": description,
        "evidence": evidences,
    }


def extract_active_and_binding_sites(payload: Dict) -> Dict[str, List[Dict]]:
    """Extract active site and binding site features from a UniProt entry."""
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
    """Fetch active site information from UniProt REST API."""
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
            "note": "No active site or binding site annotation found in UniProt" if not (active_count or binding_count) else None,
        }
    except requests.exceptions.Timeout:
        print("✗ Timeout")
        return None
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return None


def extract_uniprot_ids_from_json(json_file: str) -> list[str]:
    """Extract UniProt IDs from extracted results JSON."""
    with open(json_file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [item["uniprot_id"] for item in data]


def create_ground_truth(input_json: str, output_json: str, delay: float = 0.5):
    """Create ground truth JSON by fetching active-site annotations from UniProt."""
    print("=" * 60)
    print("Creating Ground Truth JSON for Active Site Query Task")
    print("=" * 60)

    print(f"\n📖 Reading UniProt IDs from: {input_json}")
    uniprot_ids = extract_uniprot_ids_from_json(input_json)
    print(f"✓ Found {len(uniprot_ids)} UniProt IDs")

    print("\n📋 UniProt IDs to fetch:")
    for index, uid in enumerate(uniprot_ids, 1):
        print(f"  {index:2d}. {uid}")

    print("\n🌐 Fetching data from UniProt database...")
    print(f"⏱️ Delay between requests: {delay}s\n")

    ground_truth = {}
    success_count = 0
    failed_ids = []
    empty_ids = []

    for index, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{index}/{len(uniprot_ids)}] ", end="")
        info = fetch_uniprot_active_sites(uniprot_id)

        if info is None:
            failed_ids.append(uniprot_id)
            ground_truth[uniprot_id] = {
                "has_site_annotations": False,
                "active_sites": [],
                "binding_sites": [],
                "note": "Failed to fetch from UniProt - please verify manually",
            }
        else:
            ground_truth[uniprot_id] = info
            success_count += 1
            if not info["has_site_annotations"]:
                empty_ids.append(uniprot_id)

        if index < len(uniprot_ids):
            time.sleep(delay)

    ground_truth["_metadata"] = {
        "total_entries": len(uniprot_ids),
        "successfully_fetched": success_count,
        "failed_fetches": len(failed_ids),
        "entries_without_site_annotations": len(empty_ids),
        "source": "UniProt REST API",
        "task": "active_site_query",
    }

    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Saving ground truth to: {output_path}")
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("✅ Ground Truth Creation Complete!")
    print(f"{'=' * 60}")
    print("📊 Summary:")
    print(f"  - Total entries: {len(uniprot_ids)}")
    print(f"  - Successfully fetched: {success_count}")
    print(f"  - Failed: {len(failed_ids)}")
    print(f"  - No site annotation: {len(empty_ids)}")

    if failed_ids:
        print("\n⚠️ Failed IDs (need manual verification):")
        for uid in failed_ids:
            print(f"  - {uid}")

    if empty_ids:
        print("\nℹ️ IDs without active-site or binding-site annotation in UniProt:")
        for uid in empty_ids:
            print(f"  - {uid}")

    print(f"\n📄 Output file: {output_path}")


def main():
    """Main function."""
    input_json = resolve_input_json()
    output_json = "./files/active_site_ground_truth.json"
    create_ground_truth(input_json, output_json, delay=0.5)


if __name__ == "__main__":
    main()