"""Reported or sequence-derived average protein molecular mass in Da."""
from math import fsum

# Average free amino-acid masses (Da), as used by Bio.Data.IUPACData.
AMINO_ACID_MASS = {
    "A": 89.0932, "C": 121.1582, "D": 133.1027, "E": 147.1293, "F": 165.1891,
    "G": 75.0666, "H": 155.1546, "I": 131.1729, "K": 146.1876, "L": 131.1729,
    "M": 149.2113, "N": 132.1179, "O": 255.3134, "P": 115.1305, "Q": 146.1445,
    "R": 174.2010, "S": 105.0926, "T": 119.1192, "U": 168.0532, "V": 117.1463,
    "W": 204.2252, "Y": 181.1885,
}


def sequence_mass(sequence):
    mass = sequence.get("molWeight")
    mass_source = "UniProt" if mass is not None else None
    note = None
    if mass is None:
        try:
            residues = sequence.get("value")
            if not residues:
                raise ValueError("No sequence")
            mass = round(fsum(AMINO_ACID_MASS[r] for r in residues) - (len(residues) - 1) * 18.0153)
            mass_source = "Calculated from the returned unmodified sequence (average mass, Da)"
        except (ValueError, KeyError):
            note = "No reported mass. A complete unambiguous sequence or a UniProt entry with a reported mass is required."

    return mass, mass_source, note
