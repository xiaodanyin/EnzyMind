import asyncio
from unittest.mock import patch

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from gateway import structure_jobs, workspace
from gateway.main import app
from gateway.workspace_store import WorkspaceStore


def test_long_jobs_have_private_receipts_and_a_single_result(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "_store", WorkspaceStore(tmp_path / "workspace.sqlite"))
    monkeypatch.setattr(structure_jobs, "SYNC_WAIT", 0)
    monkeypatch.setenv("ENZYMIND_RETENTION_ARTIFACT_ROOTS", "[]")
    async def slow(*args, **kwargs):
        assert kwargs["body"] == b'{"query": "P12345"}'
        await asyncio.sleep(.02)
        return JSONResponse({"success": True, "sequence_length": 430, "pdb_path": "test.pdb"})
    with TestClient(app) as client, patch("gateway.main.proxy_request", side_effect=slow) as worker:
        receipt = client.post("/api/predict/structure", json={"query":"P12345"})
        assert receipt.status_code == 202 and receipt.json()["status"] == "running"
        location = receipt.headers["location"]
        assert client.get(location).status_code == 401
        assert client.get(location, headers={"X-Enzymind-Client":"x"*64}).status_code == 404
        key = {"X-Enzymind-Client": receipt.json()["poll_token"]}
        client.portal.call(asyncio.sleep, .06)
        done = client.get(location, headers=key)
        assert done.status_code == 200 and done.json()["success"] and done.json()["sequence_length"] == 430
        assert done.json()["workspace_result"]["id"] == receipt.json()["job_id"]
        assert "poll_token" not in done.json() and worker.await_count == 1


def test_failure_keeps_worker_status_and_short_missing_input_is_422(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "_store", WorkspaceStore(tmp_path / "workspace.sqlite"))
    monkeypatch.setenv("ENZYMIND_RETENTION_ARTIFACT_ROOTS", "[]")
    with TestClient(app) as client, patch("gateway.main.proxy_request", return_value=JSONResponse(
            {"success":False, "error_code":"structure_oom", "error":"Out of memory."},status_code=503)):
        assert client.post("/api/predict/structure", json={}).json()["error_code"] == "invalid_input"
        r = client.post("/api/predict/structure", json={"query":"P01308"})
        assert r.status_code == 503 and r.json()["status"] == "failed"
        assert r.json()["error_code"] == "structure_oom"
