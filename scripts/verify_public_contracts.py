"""Check public validation and the Help examples against a running EnzyMind Gateway."""
import argparse
import json
from pathlib import Path
import re
import urllib.error
import urllib.request


def request(base, path, body):
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, json.load(response)


def verify(base):
    root = Path(__file__).resolve().parents[1]
    examples = json.loads((root / "frontend/src/config/apiExamples.json").read_text())
    paths = re.findall(r"^    path: '([^']+)',", (root / "frontend/src/views/Help.vue").read_text(), re.M)
    assert len(paths) >= 18
    for path in paths:
        status, data = request(base, path, {})
        assert status == 422 and data.get("error_code") == "invalid_input", (path, status, data)
        assert all(item["loc"] and item["msg"] for item in data["detail"]), path
    for accession, mass in [("P12345", 47409), ("P00761", 24409)]:
        for endpoint, key in [("features","sites"), ("catalytic-activity","activities")]:
            status, data = request(base, "/query/"+endpoint, {"query": accession})
            assert status == 200 and data["success"] and data["count"] == len(data[key]) > 0
            for row in data[key]:
                if key == "sites":
                    bounds = [row["start"], row["end"]]
                    assert all(v is None or type(v) is int and v >= 1 for v in bounds)
                    assert None in bounds or bounds[0] <= bounds[1]
                else:
                    assert isinstance(row["reaction_name"], str)
                    assert row["ec_number"] is None or isinstance(row["ec_number"], str)
            if accession == "P12345":
                for sample in examples[endpoint][key]:
                    # Additional versioned annotation fields may accompany the documented fields.
                    assert any(all(k in row and row[k] == v for k, v in sample.items())
                               for row in data[key]), (endpoint, sample)
        status, seq = request(base, "/query/sequence-info", {"uniprot_id": accession})
        assert status == 200 and seq["molWeight"] == mass and seq["length"] == len(seq["value"])
        status, info = request(base, "/query/enzyme-info", {"uniprot_id": accession})
        assert status == 200 and info["sequence_info"]["mol_weight"] == mass
    status, params = request(base, "/query/protein-params", {"query": "MKFLILLFNILCLFPVLAADNHGVGPQGAS"})
    assert status == 200 and isinstance(params["result"], str)
    for key in examples["protein-params"]["data"]["parameters"]:
        assert isinstance(params["data"]["parameters"][key], (int,float))
    print(f"{len(paths)} validation contracts and all sample responses passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Gateway API prefix, including /api")
    verify(parser.parse_args().base)
