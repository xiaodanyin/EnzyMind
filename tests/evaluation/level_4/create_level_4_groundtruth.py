import json
import requests
import time
from typing import List, Optional

def query_uniprot_ec_numbers(uniprot_id: str) -> Optional[List[str]]:
    """
    Query UniProt API to get EC numbers for a given UniProt ID
    """
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract EC numbers from protein description
            ec_numbers = []
            
            # Check proteinDescription -> recommendedName -> ecNumber
            if 'proteinDescription' in data:
                protein_desc = data['proteinDescription']
                
                # Recommended name
                if 'recommendedName' in protein_desc:
                    rec_name = protein_desc['recommendedName']
                    if 'ecNumbers' in rec_name:
                        for ec in rec_name['ecNumbers']:
                            if 'value' in ec:
                                ec_numbers.append(ec['value'])
                
                # Alternative names
                if 'alternativeNames' in protein_desc:
                    for alt_name in protein_desc['alternativeNames']:
                        if 'ecNumbers' in alt_name:
                            for ec in alt_name['ecNumbers']:
                                if 'value' in ec:
                                    ec_numbers.append(ec['value'])
            
            # Remove duplicates while preserving order
            ec_numbers = list(dict.fromkeys(ec_numbers))
            
            return ec_numbers if ec_numbers else None
        
        elif response.status_code == 404:
            print(f"  ⚠️  {uniprot_id}: Not found in UniProt")
            return None
        else:
            print(f"  ⚠️  {uniprot_id}: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"  ❌ {uniprot_id}: Query failed - {str(e)}")
        return None


def create_ground_truth_from_test_file(test_file_path: str, output_file: str):
    """
    Create ground truth JSON from test file
    """
    print("📖 Reading test file...")
    
    ground_truth = {}
    
    with open(test_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"✓ Found {len(lines)} entries\n")
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        parts = line.split('\t')
        if len(parts) < 2:
            print(f"⚠️  Line {i}: Invalid format, skipping")
            continue
        
        uniprot_id = parts[0]
        is_enzyme = int(parts[1]) == 1
        
        print(f"🔍 Processing {i}/{len(lines)}: {uniprot_id} (is_enzyme={is_enzyme})")
        
        fasta_file = f"{i}.fasta"
        
        ec_numbers = None
        if is_enzyme:
            # Query UniProt for EC numbers
            ec_numbers = query_uniprot_ec_numbers(uniprot_id)
            
            if ec_numbers:
                print(f"   ✓ EC numbers found: {', '.join(ec_numbers)}")
            else:
                print(f"   ⚠️  No EC numbers found (might be an enzyme without EC annotation)")
        else:
            print(f"   ✓ Not an enzyme (no EC query needed)")
        
        ground_truth[fasta_file] = {
            "is_enzyme": is_enzyme,
            "ec_numbers": ec_numbers,
            "uniprot_id": uniprot_id,
            "notes": f"Generated from UniProt {uniprot_id}"
        }
        
        # Be nice to UniProt API - rate limiting
        time.sleep(0.5)
        print()
    
    # Save ground truth
    print(f"💾 Saving ground truth to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Ground truth created successfully!")
    print(f"📊 Summary:")
    print(f"   - Total entries: {len(ground_truth)}")
    print(f"   - Enzymes: {sum(1 for v in ground_truth.values() if v['is_enzyme'])}")
    print(f"   - Non-enzymes: {sum(1 for v in ground_truth.values() if not v['is_enzyme'])}")
    print(f"   - Enzymes with EC numbers: {sum(1 for v in ground_truth.values() if v['is_enzyme'] and v['ec_numbers'])}")
    
    return ground_truth


if __name__ == "__main__":
    import os
    
    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(script_dir, "../../data/level_4/level_4_test.txt")
    output_file = os.path.join(script_dir, "level_4_ground_truth.json")
    
    print("=" * 60)
    print("Level 4 Ground Truth Generator")
    print("=" * 60)
    print()
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        exit(1)
    
    create_ground_truth_from_test_file(test_file, output_file)
