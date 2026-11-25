"""Offline EC nomenclature and reactions from the attributed ENZYME snapshot."""
import json
import re
from functools import lru_cache
from pathlib import Path

REFERENCE_FILE = Path(__file__).resolve().parents[1] / "data" / "ec-reference.json"
UNIPROT = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[0-9]+)?", re.I)


def normalize_ec(query):
    value = re.sub(r"^EC\s*:?\s*", "", query.strip(), flags=re.I)
    if not re.fullmatch(r"[1-7]\.(?:[0-9]+|-)\.(?:[0-9]+|-)\.(?:[0-9]+|-)", value):
        return None
    parts = value.split('.')
    if '-' in parts and any(part != '-' for part in parts[parts.index('-'):]):
        return None
    return '.'.join(str(int(part)) if part != '-' else '-' for part in parts)


@lru_cache(maxsize=1)
def reference():
    return json.loads(REFERENCE_FILE.read_text())


def query_ec_info(code):
    data = reference()
    source = {key: value for key, value in data.items() if key not in ('names', 'activities')}
    name = data['names'].get(code)
    if not name:
        return {'success': False, 'ec_number': code, 'activities': [], 'count': 0,
                'error': f'EC {code} is not present in ENZYME release {data["release"]}.',
                'code': 'ec_not_in_reference', 'source': source}
    parts = code.split('.')
    hierarchy = []
    for index, label in enumerate(('Class', 'Subclass', 'Sub-subclass', 'Accepted enzyme name')):
        prefix = '.'.join(parts[:index + 1] + ['-'] * (3 - index))
        specified = '-' not in parts[:index + 1]
        hierarchy.append({'label': label, 'ec_number': prefix,
                          'name': data['names'].get(prefix) if specified else None,
                          'specified': specified})
    status = ('transferred' if name.startswith('Transferred entry:') else
              'deleted' if name.startswith('Deleted entry') else
              'class' if '-' in parts else 'active')
    reaction = data.get('activities', {}).get(code)
    activities = [{'ec_number': code, 'reaction_name': reaction}] if reaction else []
    markdown = f'## EC {code}: {name}\n\n'
    markdown += '\n'.join(f'- {row["label"]}: {row["name"]}' for row in hierarchy if row['specified'] and row['name'])
    if reaction:
        markdown += f'\n\n### Catalytic activity\n\n{reaction}'
    markdown += f'\n\nSource: ENZYME, release {data["release"]} (SIB; CC BY 4.0).'
    return {'success': True, 'ec_number': code, 'name': name, 'status': status,
            'hierarchy': hierarchy, 'activities': activities, 'count': len(activities),
            'markdown': markdown, 'result': markdown, 'source': source, 'error': None}
