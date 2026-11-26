"""
Create ground truth JSON for kinetic parameters query task.
Fetch curated kinetic parameter annotations from UniProt REST API.
"""

import json
import time
from typing import Dict, List, Optional

import requests


def fetch_uniprot_kinetic_parameters(uniprot_id: str) -> Optional[Dict]:
    """Fetch kinetic parameter information from UniProt REST API."""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    try:
        print(f"🔍 Fetching {uniprot_id}...", end=" ")
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print(f"✗ HTTP {response.status_code}")
            return None

        payload = response.json()
        kinetics = extract_kinetic_parameters(payload)
        print(
            f"✓ (Km: {len(kinetics['km'])}, "
            f"Vmax: {len(kinetics['vmax'])}, "
            f"kcat note: {'yes' if kinetics['kcat_note'] else 'no'})"
        )
        return {
            "has_kinetics": bool(kinetics["km"] or kinetics["vmax"] or kinetics["kcat_note"]),
            "km": kinetics["km"],
            "vmax": kinetics["vmax"],
            "kcat_note": kinetics["kcat_note"],
            "note": "No kinetic parameter annotation found in UniProt" if not (kinetics["km"] or kinetics["vmax"] or kinetics["kcat_note"]) else None,
        }
    except requests.exceptions.Timeout:
        print("✗ Timeout")
        return None
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return None


def extract_kinetic_parameters(payload: Dict) -> Dict[str, List[Dict[str, Optional[str]]] | Optional[str]]:
    """Extract kinetic parameter annotations from UniProt entry payload."""
    km_entries: List[Dict[str, Optional[str]]] = []
    vmax_entries: List[Dict[str, Optional[str]]] = []
    kcat_note: Optional[str] = None

    for comment in payload.get("comments", []):
        if comment.get("commentType") != "BIOPHYSICOCHEMICAL PROPERTIES":
            continue

        kinetic_parameters = comment.get("kineticParameters") or {}

        for km in kinetic_parameters.get("michaelisConstants", []):
            km_entries.append(
                {
                    "value": km.get("constant"),
                    "unit": km.get("unit"),
                    "substrate": km.get("substrate"),
                }
            )

        for vmax in kinetic_parameters.get("maximumVelocities", []):
            vmax_entries.append(
                {
                    "value": vmax.get("velocity"),
                    "unit": vmax.get("unit"),
                    "substrate": vmax.get("substrate"),
                }
            )

        texts = kinetic_parameters.get("note", {}).get("texts", [])
        kcat_note = "\n".join(text.get("value", "") for text in texts).strip() or None
        break

    return {
        "km": km_entries,
        "vmax": vmax_entries,
        "kcat_note": kcat_note,
    }


def extract_uniprot_ids_from_json(json_file: str) -> list[str]:
    """Extract UniProt IDs from extracted results JSON."""
    with open(json_file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [item["uniprot_id"] for item in data]


def create_ground_truth(input_json: str, output_json: str, delay: float = 0.5):
    """Create ground truth JSON by fetching kinetic parameter annotations from UniProt."""
    print("=" * 60)
    print("Creating Ground Truth JSON for Kinetic Parameters Query Task")
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
    no_kinetics_ids = []

    for index, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{index}/{len(uniprot_ids)}] ", end="")
        info = fetch_uniprot_kinetic_parameters(uniprot_id)

        if info is None:
            failed_ids.append(uniprot_id)
            ground_truth[uniprot_id] = {
                "has_kinetics": False,
                "km": [],
                "vmax": [],
                "kcat_note": None,
                "note": "Failed to fetch from UniProt - please verify manually",
            }
        else:
            ground_truth[uniprot_id] = info
            success_count += 1
            if not info["has_kinetics"]:
                no_kinetics_ids.append(uniprot_id)

        if index < len(uniprot_ids):
            time.sleep(delay)

    ground_truth["_metadata"] = {
        "total_entries": len(uniprot_ids),
        "successfully_fetched": success_count,
        "failed_fetches": len(failed_ids),
        "entries_without_kinetics": len(no_kinetics_ids),
        "source": "UniProt REST API",
        "task": "kinetic_parameters_query",
    }

    print(f"\n💾 Saving ground truth to: {output_json}")
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("✅ Ground Truth Creation Complete!")
    print(f"{'=' * 60}")
    print("📊 Summary:")
    print(f"  - Total entries: {len(uniprot_ids)}")
    print(f"  - Successfully fetched: {success_count}")
    print(f"  - Failed: {len(failed_ids)}")
    print(f"  - No kinetic parameter annotation: {len(no_kinetics_ids)}")

    if failed_ids:
        print("\n⚠️ Failed IDs (need manual verification):")
        for uid in failed_ids:
            print(f"  - {uid}")

    if no_kinetics_ids:
        print("\nℹ️ IDs without kinetic parameter annotation in UniProt:")
        for uid in no_kinetics_ids:
            print(f"  - {uid}")

    print(f"\n📄 Output file: {output_json}")


def main():
    """Main function."""
    input_json = "./files/extracted_enzymind_results.json"
    output_json = "./files/kinetic_parameters_ground_truth.json"
    create_ground_truth(input_json, output_json, delay=0.5)


if __name__ == "__main__":
    main()