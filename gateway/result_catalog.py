"""Shared tool catalog and compact, traceable evidence for the workspace."""
import re
from urllib.parse import unquote, urlsplit

RESULT_UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"


def normalize_result_links(text, owned_records):
    """Repair model-written link destinations only for verified owned records.

    Models sometimes emit a bare UUID or invent a hostname for a valid record.
    The database supplies the canonical URL; unknown IDs and unrelated links
    are never turned into saved scientific evidence.
    """
    def placeholder(target):
        try:
            host = (urlsplit(unquote(target)).hostname or '').lower().rstrip('.')
            return host == 'invalid' or host.endswith('.invalid')
        except ValueError:
            return False

    def destination(target):
        placeholder_host = re.fullmatch(r"https?://enzymind\.c?(" + RESULT_UUID + r")", target, re.I)
        try:
            path = placeholder_host.group(1) if placeholder_host else urlsplit(target).path.rstrip('/')
        except ValueError:
            return None
        found = re.search(r"(" + RESULT_UUID + r")$", path, re.I)
        if not found:
            return None
        result_id = found.group(1).lower()
        # Some model replies put the ID in a fabricated hostname instead of
        # the path, occasionally with an extra "c" before the UUID. Accept
        # only this observed EnzyMind placeholder shape and a verified ID.
        if result_id not in owned_records or not (path.lower() == result_id or path.lower().endswith('/' + result_id) or placeholder_host):
            return None
        return owned_records[result_id]['url']

    def clean(prose):
        def inline(match):
            label, target = match.group(1), match.group(2)
            canonical = destination(target)
            if canonical:
                return f'[{label}]({canonical})'
            # A placeholder without a verified ID cannot be assigned to a
            # result just because its label sounds similar. Keep the prose.
            return label if placeholder(target) else match.group(0)
        prose = re.sub(r'''\[([^\]\n]+)\]\(\s*<?([^\s<>\)]+)>?(?:\s+["'][^\n]*?["'])?\s*\)''', inline, prose)
        missing = set()
        def reference(match):
            label, target = match.group(1), match.group(2)
            canonical = destination(target)
            if canonical:
                return f'[{label}]: {canonical}'
            if placeholder(target):
                missing.add(' '.join(label.lower().split()))
                return ''
            return match.group(0)
        prose = re.sub(r'^ {0,3}\[([^\]\n]+)\]:\s*<?([^\s<>]+)>?[^\n]*$', reference, prose, flags=re.M)
        if missing:
            def remove_reference(match):
                label, ref = match.group(1), match.group(2)
                return label if ' '.join((ref or label).lower().split()) in missing else match.group(0)
            prose = re.sub(r'\[([^\]\n]+)\](?:\[([^\]\n]*)\])?', remove_reference, prose)
        def bare(match):
            target = match.group(0).removeprefix('<').removesuffix('>')
            target = target.rstrip('.,;:!?，。；！')
            if not placeholder(target):
                return match.group(0)
            canonical = destination(target)
            return f'[Saved result]({canonical})' if canonical else ''
        prose = re.sub(r'<?(?:https?://|//)[^\s<>\[\]()]+>?', bare, prose, flags=re.I)
        return re.sub(r"(\[[^\]\n]+\]\(/enzymind/results/(" + RESULT_UUID + r")\))\s+<?/enzymind/results/\2>?\)?", r"\1", prose, flags=re.I)

    # Quoted code can discuss a bad address; it is not a clickable citation.
    pieces = re.split(r'(```[\s\S]*?```|`[^`\n]+`)', text or '')
    return ''.join(piece if index % 2 else clean(piece) for index, piece in enumerate(pieces))

# key: service, upstream path, title, evidence category
TOOLS = {
    "python": ("python_sandbox", "/jobs", "Python analysis", "代码计算结果"),
    "recognize": ("enzy_recognize", "/api/recognize/enzyme", "Enzyme recognition", "Prediction"),
    "ec": ("ecnumber_predict", "/api/predict/ec", "EC classification", "Prediction"),
    "substrate": ("substrate_predict", "/api/predict/substrate", "Substrate compatibility", "Prediction"),
    "kcat": ("kcat_predict", "/api/predict/kcat", "Catalytic turnover · kcat", "Prediction"),
    "km": ("km_predict", "/api/predict/km", "Michaelis constant · Km", "Prediction"),
    "structure": ("structure_predict", "/api/predict/structure", "Protein structure", "Predicted structure"),
    "active-sites": ("active_sites", "/api/predict/active-sites", "Functional sites · EasIFA", "Prediction"),
    "enzyme-type": ("enzyme_type", "/api/query/enzyme-type", "Enzyme recommendation", "Prediction"),
    "parameters": ("protparam", "/query/protein-physchem", "Sequence properties", "Calculated properties"),
    "blast": ("sequence_alignment", "/api/query/blast", "Sequence similarity · BLAST", "Sequence alignment"),
    "function": ("function_get", "/api/query/function", "Protein function", "Database annotation"),
    "subclass": ("enzyme_subclass", "/api/query/enzyme-subclass", "Enzyme subclass", "Database annotation"),
    "reaction": ("ec_reaction_info", "/api/query/catalytic-activity", "Catalytic reactions", "Database annotation"),
    "check": ("enzyme_check", "/api/check/enzyme", "Enzyme annotation", "Database annotation"),
    "enzyme-info": ("enzyme_full_info", "/api/query/enzyme-full-info", "Enzyme information", "Database annotation"),
    "features": ("functional_site", "/api/query/features", "Annotated functional sites", "Database annotation"),
    "kinetics": ("kinetic_params", "/api/query/kinetics", "Reported kinetic parameters", "Database annotation"),
    "sequence": ("sequence_info", "/api/query/sequence-info", "Protein sequence", "Database annotation"),
    "mcsa-query": ("query_mechanism_mcsa", "/api/enzyme/query", "M-CSA enzyme records", "Database annotation"),
    "mcsa-mechanism": ("query_mechanism_mcsa", "/api/enzyme/mechanism/summary", "M-CSA catalytic mechanism", "Database annotation"),
    "mcsa-steps": ("query_mechanism_mcsa", "/api/enzyme/mechanism/steps", "M-CSA mechanism steps", "Database annotation"),
    "mcsa-residues": ("query_mechanism_mcsa", "/api/enzyme/active_sites", "M-CSA catalytic residues", "Database annotation"),
    "mcsa-reaction": ("query_mechanism_mcsa", "/api/enzyme/reaction", "M-CSA reaction", "Database annotation"),
    "mcsa-cofactors": ("query_mechanism_mcsa", "/api/enzyme/cofactors", "M-CSA cofactors", "Database annotation"),
    "mcsa-electron-flow": ("query_mechanism_mcsa", "/api/enzyme/mechanism/electron_flows/summary", "M-CSA electron flow", "Database annotation"),
}


def tool_for_service(service):
    return next((key for key, value in TOOLS.items() if value[0] == service), service)


def payload_error(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("error") or payload.get("success") is False or payload.get("status") in ("failed", "error"):
        return str(payload.get("error") or payload.get("message") or "The analysis did not complete.")
    result = payload.get("result")
    if isinstance(result, str) and result.lstrip().startswith(("[ERROR]", "❌")):
        return result.strip()
    for field in ("result", "data"):
        nested = payload.get(field)
        if isinstance(nested, dict):
            error = payload_error(nested)
            if error:
                return error
    return None


def compact(value, depth=0):
    """Limit model context, preserving the complete record separately in SQLite."""
    if depth > 6:
        return "[Open the saved record for nested data]"
    if isinstance(value, dict):
        omitted = {"structure_data", "pdb", "pdb_content", "pdb_text", "html", "structure_html"}
        if "sequence_normalization" in value:
            # Display blocks contain presentation-only colours/end labels and
            # are paginated by compact(). Supply the full length explicitly and
            # the biological sequence instead; keep blocks in the saved record.
            omitted.add("enzyme_sequence_info")
        if "active_data" in value or "residue_labels" in value:
            # EasIFA's raw class vectors lack class-order metadata in historical
            # records. They must not be confused with explicitly labelled sites.
            omitted.update({"scores", "pred_active_site_labels", "residue_labels"})
        return {k: compact(v, depth + 1) for k, v in value.items()
                if k not in omitted}
    if isinstance(value, list):
        result = [compact(v, depth + 1) for v in value[:30]]
        if len(value) > 30:
            result.append({"additional_records": len(value) - 30})
        return result
    if isinstance(value, str) and len(value) > 3000:
        return value[:3000] + "\n[Excerpt; full data in the saved result]"
    return value


def cited_results(text):
    return list(dict.fromkeys(re.findall(r"/enzymind/results/([a-f0-9-]{36})\b", text or "")))
