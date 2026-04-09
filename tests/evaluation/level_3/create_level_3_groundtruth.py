import json
import os
import re
import time
from typing import Dict, List, Optional

import nbformat
import requests


def extract_uniprot_ids_from_notebook(notebook_path: str) -> List[str]:
    pattern = (
        r"Please check whether\s+([A-Z0-9]+)\s+is annotated as an enzyme in public databases"
    )

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


def extract_ec_numbers(payload: Dict) -> List[str]:
    ec_numbers: List[str] = []

    protein_description = payload.get("proteinDescription") or {}
    recommended_name = protein_description.get("recommendedName") or {}
    submitted_names = protein_description.get("submissionNames") or []
    alternative_names = protein_description.get("alternativeNames") or []

    for block in [recommended_name, *submitted_names, *alternative_names]:
        for ec in block.get("ecNumbers", []) or []:
            value = ec.get("value")
            if value and value not in ec_numbers:
                ec_numbers.append(value)

    for comment in payload.get("comments", []):
        if comment.get("commentType") != "CATALYTIC ACTIVITY":
            continue
        reaction = comment.get("reaction") or {}
        value = reaction.get("ecNumber")
        if value and value not in ec_numbers:
            ec_numbers.append(value)

    return ec_numbers


def extract_catalytic_activities(payload: Dict) -> List[Dict[str, Optional[str]]]:
    activities: List[Dict[str, Optional[str]]] = []

    for comment in payload.get("comments", []):
        if comment.get("commentType") != "CATALYTIC ACTIVITY":
            continue

        reaction = comment.get("reaction") or {}
        activity = {
            "reaction_name": reaction.get("name", ""),
            "ec_number": reaction.get("ecNumber"),
            "rhea_id": None,
        }

        for ref in reaction.get("reactionCrossReferences", []):
            if ref.get("database") == "Rhea":
                rhea_id = ref.get("id")
                activity["rhea_id"] = rhea_id.replace("RHEA:", "") if rhea_id else None
                break

        activities.append(activity)

    return activities


def extract_kinetic_parameters(payload: Dict) -> Dict[str, object]:
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
        "has_kinetics": bool(km_entries or vmax_entries or kcat_note),
        "km": km_entries,
        "vmax": vmax_entries,
        "kcat_note": kcat_note,
    }


def extract_site_entry(feature: Dict) -> Dict:
    location = feature.get("location", {})
    return {
        "start": location.get("start", {}).get("value"),
        "end": location.get("end", {}).get("value"),
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
        "has_site_annotations": bool(active_sites or binding_sites),
        "active_sites": active_sites,
        "binding_sites": binding_sites,
    }


def fetch_uniprot_level3_info(uniprot_id: str, retries: int = 3, retry_delay: float = 1.0) -> Optional[Dict]:
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    print(f"🔍 Fetching {uniprot_id}...", end=" ")

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                print(f"✗ HTTP {response.status_code}")
                return None

            payload = response.json()
            ec_numbers = extract_ec_numbers(payload)
            catalytic_activities = extract_catalytic_activities(payload)
            kinetics = extract_kinetic_parameters(payload)
            site_info = extract_active_and_binding_sites(payload)
            is_enzyme = bool(ec_numbers or catalytic_activities)

            print(
                "✓ "
                f"(enzyme: {'yes' if is_enzyme else 'no'}, "
                f"EC: {len(ec_numbers)}, "
                f"rxn: {len(catalytic_activities)}, "
                f"Km: {len(kinetics['km'])}, "
                f"Vmax: {len(kinetics['vmax'])}, "
                f"site: {len(site_info['active_sites']) + len(site_info['binding_sites'])})"
            )

            return {
                "fetch_failed": False,
                "is_enzyme": is_enzyme,
                "ec_numbers": ec_numbers,
                "has_activity": bool(catalytic_activities),
                "activities": catalytic_activities,
                "has_kinetics": kinetics["has_kinetics"],
                "km": kinetics["km"],
                "vmax": kinetics["vmax"],
                "kcat_note": kinetics["kcat_note"],
                "has_site_annotations": site_info["has_site_annotations"],
                "active_sites": site_info["active_sites"],
                "binding_sites": site_info["binding_sites"],
            }
        except requests.exceptions.RequestException as exc:
            if attempt < retries:
                print(f"retry {attempt}/{retries} ({exc.__class__.__name__})...", end=" ")
                time.sleep(retry_delay)
            else:
                print(f"✗ {exc.__class__.__name__}")
                return None


def create_ground_truth(notebook_path: str, output_json: str, delay: float = 0.5) -> Dict:
    print("=" * 60)
    print("Creating Ground Truth JSON for Level 3 Task")
    print("=" * 60)

    print(f"\n📖 Reading UniProt IDs from: {notebook_path}")
    uniprot_ids = extract_uniprot_ids_from_notebook(notebook_path)
    print(f"✓ Found {len(uniprot_ids)} UniProt IDs")

    ground_truth = {}
    success_count = 0
    failed_ids = []

    for index, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{index}/{len(uniprot_ids)}] ", end="")
        info = fetch_uniprot_level3_info(uniprot_id)

        if info is None:
            failed_ids.append(uniprot_id)
            ground_truth[uniprot_id] = {
                "fetch_failed": True,
                "is_enzyme": False,
                "ec_numbers": [],
                "has_activity": False,
                "activities": [],
                "has_kinetics": False,
                "km": [],
                "vmax": [],
                "kcat_note": None,
                "has_site_annotations": False,
                "active_sites": [],
                "binding_sites": [],
            }
        else:
            ground_truth[uniprot_id] = info
            success_count += 1

        with open(output_json, "w", encoding="utf-8") as handle:
            json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

        if index < len(uniprot_ids):
            time.sleep(delay)

    ground_truth["_metadata"] = {
        "total_entries": len(uniprot_ids),
        "successfully_fetched": success_count,
        "failed_fetches": len(failed_ids),
        "failed_ids": failed_ids,
        "source": "UniProt REST API",
        "task": "level_3",
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    print(f"\n💾 Saving ground truth to: {output_json}")
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(ground_truth, handle, indent=2, ensure_ascii=False)

    print("\n✅ Ground truth created successfully")
    print(f"  Total entries: {len(uniprot_ids)}")
    print(f"  Successfully fetched: {success_count}")
    print(f"  Failed: {len(failed_ids)}")
    return ground_truth


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    notebook_path = os.path.join(script_dir, "../../enzymind_test_level_3.ipynb")
    output_file = os.path.join(script_dir, "files/level_3_ground_truth.json")

    if not os.path.exists(notebook_path):
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    create_ground_truth(notebook_path, output_file, delay=0.5)