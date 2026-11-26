"""
Create ground truth JSON file for sequence query task
Fetches amino acid sequence, length, and molecular weight from UniProt database
"""
import json
import requests
import time
from typing import Dict, Optional


def fetch_uniprot_sequence_info(uniprot_id: str) -> Optional[Dict]:
    """
    Fetch sequence information from UniProt REST API
    
    Args:
        uniprot_id: UniProt accession ID
        
    Returns:
        Dictionary with sequence, length, and molecular weight, or None if failed
    """
    # UniProt REST API endpoint
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
    
    try:
        print(f"🔍 Fetching {uniprot_id}...", end=" ")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract sequence
            sequence = data.get('sequence', {}).get('value', '')
            sequence_length = data.get('sequence', {}).get('length', 0)
            molecular_weight = data.get('sequence', {}).get('molWeight', 0)
            
            print(f"✓ (Length: {sequence_length}, MW: {molecular_weight:.2f} Da)")
            
            return {
                'amino_acid_sequence': sequence,
                'sequence_length': sequence_length,
                'molecular_weight': molecular_weight
            }
        else:
            print(f"✗ HTTP {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def extract_uniprot_ids_from_json(json_file: str) -> list:
    """
    Extract UniProt IDs from the extracted results JSON file
    
    Args:
        json_file: Path to the JSON file containing test results
        
    Returns:
        List of UniProt IDs in order
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    uniprot_ids = [item['uniprot_id'] for item in data]
    return uniprot_ids


def create_ground_truth(input_json: str, output_json: str, delay: float = 0.5):
    """
    Create ground truth JSON file by fetching data from UniProt
    
    Args:
        input_json: Path to extracted results JSON file
        output_json: Path to output ground truth JSON file
        delay: Delay between API requests (seconds) to avoid rate limiting
    """
    print("="*60)
    print("Creating Ground Truth JSON for Sequence Query Task")
    print("="*60)
    
    # Extract UniProt IDs
    print(f"\n📖 Reading UniProt IDs from: {input_json}")
    uniprot_ids = extract_uniprot_ids_from_json(input_json)
    print(f"✓ Found {len(uniprot_ids)} UniProt IDs")
    
    # Display IDs
    print(f"\n📋 UniProt IDs to fetch:")
    for i, uid in enumerate(uniprot_ids, 1):
        print(f"  {i:2d}. {uid}")
    
    # Fetch data from UniProt
    print(f"\n🌐 Fetching data from UniProt database...")
    print(f"⏱️  Delay between requests: {delay}s")
    print()
    
    ground_truth = {}
    success_count = 0
    failed_ids = []
    
    for i, uniprot_id in enumerate(uniprot_ids, 1):
        print(f"[{i}/{len(uniprot_ids)}] ", end="")
        
        info = fetch_uniprot_sequence_info(uniprot_id)
        
        if info:
            ground_truth[uniprot_id] = info
            success_count += 1
        else:
            failed_ids.append(uniprot_id)
            # Add placeholder for failed entries
            ground_truth[uniprot_id] = {
                'amino_acid_sequence': '',
                'sequence_length': 0,
                'molecular_weight': 0.0,
                'note': 'Failed to fetch from UniProt - please fill manually'
            }
        
        # Delay to avoid rate limiting
        if i < len(uniprot_ids):
            time.sleep(delay)
    
    # Add metadata
    ground_truth['_metadata'] = {
        'total_entries': len(uniprot_ids),
        'successfully_fetched': success_count,
        'failed_fetches': len(failed_ids),
        'source': 'UniProt REST API',
        'task': 'sequence_query'
    }
    
    # Save to JSON file
    print(f"\n💾 Saving ground truth to: {output_json}")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    
    # Summary
    print(f"\n{'='*60}")
    print("✅ Ground Truth Creation Complete!")
    print(f"{'='*60}")
    print(f"📊 Summary:")
    print(f"  - Total entries: {len(uniprot_ids)}")
    print(f"  - Successfully fetched: {success_count}")
    print(f"  - Failed: {len(failed_ids)}")
    print(f"  - Success rate: {success_count/len(uniprot_ids)*100:.1f}%")
    
    if failed_ids:
        print(f"\n⚠️  Failed IDs (need manual completion):")
        for uid in failed_ids:
            print(f"  - {uid}")
    
    print(f"\n📄 Output file: {output_json}")
    
    # Show preview of first entry
    if success_count > 0:
        first_id = uniprot_ids[0]
        if ground_truth[first_id].get('amino_acid_sequence'):
            print(f"\n👀 Preview of first entry ({first_id}):")
            info = ground_truth[first_id]
            print(f"  Sequence length: {info['sequence_length']}")
            print(f"  Molecular weight: {info['molecular_weight']:.2f} Da")
            print(f"  Sequence (first 50 chars): {info['amino_acid_sequence'][:50]}...")


def main():
    """Main function"""
    # File paths
    input_json = "./level_1_2_sequence_query/extracted_enzymind_results.json"
    output_json = "./level_1_2_sequence_query/ground_truth.json"
    
    # Create ground truth
    create_ground_truth(input_json, output_json, delay=0.5)


if __name__ == "__main__":
    main()
