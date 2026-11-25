"""Live valid-input smoke checks. Run with gateway/venv/bin/python.

Default: database queries and calculations. --predictions includes GPU jobs
and NCBI BLAST, which may take many minutes. No workspace records are created.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway.result_catalog import payload_error

SEQUENCE = "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL"
CHECKS = {
    "sequence": ("/query/sequence-info", {"uniprot_id": "P00761"}),
    "function": ("/query/function", {"query": "P00761"}),
    "check": ("/check/enzyme", {"uniprot_id": "P00761"}),
    "subclass": ("/query/enzyme-subclass", {"query": "hydrolase", "num_samples": 2}),
    "reaction": ("/query/catalytic-activity", {"query": "P00761"}),
    "features": ("/query/features", {"query": "P00761"}),
    "kinetics": ("/query/kinetics", {"query": "P00761"}),
    "enzyme-info": ("/query/enzyme-full-info", {"uniprot_id": "P00761"}),
    "parameters": ("/query/protein-physchem", {"query": SEQUENCE}),
    "enzyme-type": ("/query/enzyme-type", {"query": "CC(=O)OCC.O>>CC(=O)O.CCO"}),
    "mcsa": ("/api/enzyme/query", {"query_id": "1"}),
}
PREDICTIONS = {
    "recognize": ("/recognize/enzyme", {"input_type": "sequence", "query": SEQUENCE}),
    "ec": ("/predict/ec", {"input_type": "sequence", "query": SEQUENCE}),
    **{name: (f"/predict/{name}", {"smiles": "CCO", "enzyme_input_type": "sequence", "enzyme_query": SEQUENCE})
       for name in ("substrate", "kcat", "km")},
    "active-sites": ("/predict/active-sites", {"uniprot_id": "P00761"}),
    "structure": ("/predict/structure", {"input_type": "sequence", "query": "FVNQHLCGSHLVEALYLVCGERGFFYTPKA", "output_name": "service_check"}),
    "blast": ("/query/blast", {"query": SEQUENCE, "max_results": 1}),
}


async def main(args):
    available = {**CHECKS, **PREDICTIONS}
    selected = args.tools or list(available if args.predictions else CHECKS)
    records = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(3780, connect=15)) as client:
        for name in selected:
            if name not in available:
                raise SystemExit(f"Unknown tool {name}. Choose from: {', '.join(available)}")
            path, body = available[name]
            url = f"{args.gateway.rstrip('/')}/api{path}" if name != "mcsa" else f"http://{args.service_host}:18919{path}"
            print(f"Checking {name}…", flush=True)
            started = time.monotonic()
            try:
                response = await client.post(url, json=body)
                payload = response.json()
                error = payload_error(payload)
                record = {"tool": name, "ok": response.is_success and not error,
                          "http": response.status_code, "error": error}
            except (httpx.HTTPError, ValueError) as exc:
                record = {"tool": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            record["seconds"] = round(time.monotonic() - started, 2)
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    print(f"{sum(bool(r['ok']) for r in records)}/{len(records)} passed; report: {args.output}")
    return 0 if all(r["ok"] for r in records) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="http://127.0.0.1:8080")
    parser.add_argument("--service-host", default="127.0.0.1", help="M-CSA service host")
    parser.add_argument("--predictions", action="store_true", help="Include expensive predictions and external BLAST")
    parser.add_argument("--tools", nargs="+", help="Only the named tools; these override --predictions")
    parser.add_argument("--output", type=Path, default=Path("/tmp/enzymind-api-check.json"))
    raise SystemExit(asyncio.run(main(parser.parse_args())))
