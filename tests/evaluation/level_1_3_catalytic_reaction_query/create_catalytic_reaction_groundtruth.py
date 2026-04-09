"""
Create ground truth JSON for catalytic reaction query task.
Fetch catalytic activity annotations from UniProt REST API.
"""

import json
import time
from typing import Dict, List, Optional

import requests


def fetch_uniprot_catalytic_activity(uniprot_id: str) -> Optional[Dict]:
    """Fetch catalytic activity information from UniProt REST API."""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    try:
        print(f"🔍 Fetching {uniprot_id}...", end=" ")
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print(f"✗ HTTP {response.status_code}")
            return None

        payload = response.json()
        activities = extract_catalytic_activities(payload)
        print(f"✓ (activities: {len(activities)})")
        return {
            "has_activity": bool(activities),
            "activities": activities,
            "note": "No catalytic activity annotation found in UniProt" if not activities else None,
        }
    except requests.exceptions.Timeout:
        print("✗ Timeout")
        return None
    except Exception as exc:
        print(f"✗ Error: {exc}")
        return None


def extract_catalytic_activities(payload: Dict) -> List[Dict[str, Optional[str]]]:
    """Extract catalytic activities from UniProt entry payload."""
    activities: List[Dict[str, Optional[str]]] = []

    for comment in payload.get("comments", []):
        if comment.get("commentType") != "CATALYTIC ACTIVITY":
            continue

        reaction = comment.get("reaction") or {}
        activity = {
            "reaction_name": reaction.get("name", ""),
            "ec_number": reaction.get("ecNumber"),
            "rhea_id": None,
            "evidence": [],
        }

        for ref in reaction.get("reactionCrossReferences", []):
            if ref.get("database") == "Rhea":
                rhea_id = ref.get("id")
                activity["rhea_id"] = rhea_id.replace("RHEA:", "") if rhea_id else None
                break

        for evidence in comment.get("evidences", []):
            code = evidence.get("evidenceCode")
            if code:
                activity["evidence"].append(code)

        activities.append(activity)

    return activities


def extract_uniprot_ids_from_json(json_file: str) -> list[str]:
    """Extract UniProt IDs from extracted results JSON."""
    with open(json_file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [item["uniprot_id"] for item in data]


def create_ground_truth(input_json: str, output_json: str, delay: float = 0.5):
    """Create ground truth JSON by fetching catalytic activity from UniProt."""
    print("=" * 60)
    print("Creating Ground Truth JSON for Catalytic Reaction Query Task")
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
    no_activity_ids = []

    for index, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{index}/{len(uniprot_ids)}] ", end="")
        info = fetch_uniprot_catalytic_activity(uniprot_id)

        if info is None:
            failed_ids.append(uniprot_id)
            ground_truth[uniprot_id] = {
                "has_activity": False,
                "activities": [],
                "note": "Failed to fetch from UniProt - please verify manually",
            }
        else:
            ground_truth[uniprot_id] = info
            success_count += 1
            if not info["has_activity"]:
                no_activity_ids.append(uniprot_id)

        if index < len(uniprot_ids):
            time.sleep(delay)

    ground_truth["_metadata"] = {
        "total_entries": len(uniprot_ids),
        "successfully_fetched": success_count,
        "failed_fetches": len(failed_ids),
        "entries_without_activity": len(no_activity_ids),
        "source": "UniProt REST API",
        "task": "catalytic_reaction_query",
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
    print(f"  - No catalytic activity annotation: {len(no_activity_ids)}")

    if failed_ids:
        print("\n⚠️ Failed IDs (need manual verification):")
        for uid in failed_ids:
            print(f"  - {uid}")

    if no_activity_ids:
        print("\nℹ️ IDs without catalytic activity annotation in UniProt:")
        for uid in no_activity_ids:
            print(f"  - {uid}")

    print(f"\n📄 Output file: {output_json}")


def main():
    """Main function."""
    input_json = "./files/extracted_enzymind_results.json"
    output_json = "./files/catalytic_reaction_ground_truth.json"
    create_ground_truth(input_json, output_json, delay=0.5)


if __name__ == "__main__":
    main()