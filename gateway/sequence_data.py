"""Separate EasIFA display padding from biological sequence data.

Apply to active-site responses and saved-result reads, including older records.
Never strip arbitrary non-amino-acid characters: internal gaps/markup would make
residue positions ambiguous. Original stored payloads remain available in SQLite.
"""
import re

_LETTERS = re.compile(r"[ACDEFGHIKLMNPQRSTVWYBXZJUO]+", re.IGNORECASE)


def normalize_active_site_payload(value):
    if isinstance(value, list):
        return [normalize_active_site_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: normalize_active_site_payload(item) for key, item in value.items()}
    rows = result.get("enzyme_sequence_info")
    if not isinstance(rows, list) or not rows:
        return result
    if not all(isinstance(row, list) and row and isinstance(row[0], str) for row in rows):
        return _unavailable(result, "Malformed sequence display blocks; retrieve a standard sequence before calculating length.")
    display = "".join(row[0] for row in rows)
    sequence = display.rstrip("&")
    if not _LETTERS.fullmatch(sequence):
        return _unavailable(result, "Sequence display blocks contain internal gaps or invalid characters; do not count or remove them to infer a sequence.")
    if result.get("multi_chain"):
        return _unavailable(result, "Multiple chains are present; retrieve each chain sequence separately rather than concatenate display blocks.")
    sequence = sequence.upper()
    for field in ("sequence", "enzyme_sequence", "aa_sequence"):
        explicit = result.get(field)
        if explicit and (not isinstance(explicit, str) or explicit.upper() != sequence):
            return _unavailable(result, "The explicit sequence and display blocks disagree; retrieve a verified sequence before calculating length.")
    # Only the suffix is removed. This cannot shift any biological residue index.
    remaining, clean_rows = len(sequence), []
    for row in rows:
        if not remaining:
            break
        kept = min(remaining, len(row[0]))
        clean = list(row)
        clean[0] = row[0][:kept].upper()
        if len(clean) > 2 and isinstance(clean[2], list):
            clean[2] = clean[2][:kept]
        clean_rows.append(clean)
        remaining -= kept
    removed = len(display) - len(sequence)
    previous = result.get("sequence_normalization", {})
    # Re-reading an already normalized response must retain its provenance.
    if not removed and isinstance(previous, dict) and previous.get("status") == "normalized":
        removed = previous.get("display_padding_removed", 0)
    result.update(sequence=sequence, sequence_length=len(sequence), enzyme_sequence_info=clean_rows,
                  sequence_normalization={
                      "version": 1, "status": "normalized", "source": "enzyme_sequence_info",
                      "display_padding_removed": removed,
                      "note": "Use sequence and sequence_length for calculations. Trailing display padding is excluded; residue numbering is unchanged. This is the sequence saved with this prediction, not a fresh UniProt lookup.",
                  })
    return result


def _unavailable(result, reason):
    # Do not invent a sequence or renumber ambiguous historical data.
    result["sequence_normalization"] = {"version": 1, "status": "unavailable", "note": reason}
    return result
