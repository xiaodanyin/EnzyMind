"""Timeouts for the platform and Agent must cover the same scientific jobs."""
import os


def service_timeout(service: str) -> float:
    if service == "structure_predict":
        return max(300, int(os.getenv("ESMFOLD_TIMEOUT", "3600"))) + 60
    if service == "sequence_alignment":
        return max(960, int(os.getenv("ENZYMIND_BLAST_TIMEOUT", "120")) + 90)
    return 900
