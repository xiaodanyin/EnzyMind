#!/usr/bin/env python3
"""Build an offline EC label snapshot from ExPASy's unmodified official files.

Download enzclass.txt and enzyme.dat from https://ftp.expasy.org/databases/enzyme/
then run: python3 scripts/build_ec_reference.py /path/to/downloads
The resulting JSON includes source hashes and SIB's CC BY 4.0 attribution.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def build(source, *, include_activities=False):
    files = {name: (source / name).read_bytes() for name in ('enzclass.txt', 'enzyme.dat')}
    classes, enzymes = (files[name].decode('utf-8') for name in files)
    release = re.search(r'Release:\s+(\d{2}-[A-Za-z]{3}-\d{4})', classes)[1]
    assert f'Release of {release}' in enzymes, 'Source releases must match'
    assert enzymes.rstrip().endswith('//'), 'Truncated enzyme.dat'
    names, activities, current = {}, {}, None
    for line in classes.splitlines():
        match = re.match(r'^(\d+)\.\s*(\d+|-)\.\s*(\d+|-)\.\s*(-)\s+(.+)', line)
        if match:
            current = '.'.join(match.groups()[:4])
            names[current] = match[5].strip()
        elif current and line.startswith(' ') and line.strip():
            names[current] += ' ' + line.strip()
        else:
            current = None
    assert all(f'{i}.-.-.-' in names for i in range(1, 8))
    assert len(names) > 250
    for block in enzymes.split('//'):
        identifier = re.search(r'^ID   (\d+\.\d+\.\d+\.\d+)$', block, re.M)
        if identifier:
            name = ' '.join(re.findall(r'^DE   (.*)$', block, re.M))
            assert name, identifier[1]
            names[identifier[1]] = name
            reaction = ' '.join(re.findall(r'^CA   (.*)$', block, re.M))
            if reaction:
                activities[identifier[1]] = reaction
    assert len(names) > 6000, 'Incomplete reference'
    reference = {
        'release': release,
        'attribution': 'SIB Swiss Institute of Bioinformatics, ENZYME nomenclature database',
        'license': 'CC BY 4.0',
        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
        'sources': {f'https://ftp.expasy.org/databases/enzyme/{name}': hashlib.sha256(data).hexdigest() for name, data in files.items()},
        'names': {key: value.removesuffix('.') for key, value in names.items()},
    }
    if include_activities:
        reference['activities'] = activities
    return reference


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'frontend/src/data/ec-reference.json')
    parser.add_argument('--include-activities', action='store_true', help='Include official catalytic reactions for the EC-info service snapshot')
    args = parser.parse_args()
    reference = build(args.source, include_activities=args.include_activities)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + '\n')
    print(f"Wrote {len(reference['names'])} names from {reference['release']} to {args.output}")
