#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            env[key] = value
    return env


def _resolve_token(explicit_token: str | None, repo_root: Path, env_file: str | None) -> str | None:
    if explicit_token:
        return explicit_token

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if token:
        return token

    if env_file:
        env_path = Path(env_file)
        if not env_path.is_absolute():
            env_path = repo_root / env_path
        file_env = _load_env_file(env_path)
        token = file_env.get("HF_TOKEN") or file_env.get("HUGGINGFACE_HUB_TOKEN")
        if token:
            return token

    return None


def _load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _require_huggingface_hub() -> None:
    try:
        import huggingface_hub  # noqa: F401
    except ModuleNotFoundError:
        raise SystemExit(
            "Missing dependency: huggingface_hub\n"
            "Install with:\n"
            "  python -m pip install -U huggingface_hub\n"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download all checkpoints directories from a Hugging Face repo into this repo, "
            "preserving the original directory structure (so services can run without moving files)."
        )
    )
    parser.add_argument(
        "--manifest",
        default=str(_repo_root() / "scripts" / "hf_models_manifest.json"),
        help="Manifest JSON path (default: scripts/hf_models_manifest.json).",
    )
    parser.add_argument(
        "--repo-id",
        default=None,
        help="Hugging Face repo_id, e.g. xiaoruiwang/EnzyMind_Models (default: from manifest).",
    )
    parser.add_argument(
        "--repo-type",
        default=None,
        choices=["model", "dataset", "space"],
        help="Hugging Face repo type (default: from manifest).",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Target branch/revision on HF (default: repo default branch).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="HF access token (only needed for private/gated repos).",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional env file to load token from (default: .env). Use empty string to disable.",
    )
    parser.add_argument(
        "--use-env-token",
        action="store_true",
        help="Use token from env vars (.env optional). Default is anonymous download (no token).",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(_repo_root() / ".hf_cache"),
        help="Cache directory for HF downloads (default: .hf_cache).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if cached.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without downloading.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = _repo_root()

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    manifest = _load_manifest(manifest_path)

    repo_id = args.repo_id or manifest.get("repo_id")
    repo_type = args.repo_type or manifest.get("repo_type", "model")
    paths = manifest.get("paths") or []
    if not repo_id:
        raise SystemExit("Missing --repo-id and manifest has no repo_id.")
    if not paths:
        raise SystemExit("Manifest has no paths to download.")

    allow_patterns = [f"{p}/**" for p in paths]

    if args.dry_run:
        print(f"HF repo: {repo_type}:{repo_id}")
        for p in paths:
            print(f"DOWNLOAD: {p}")
        return

    _require_huggingface_hub()
    from huggingface_hub import snapshot_download

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.token:
        token = args.token
    elif args.use_env_token:
        env_file = args.env_file if args.env_file else None
        token = _resolve_token(None, root, env_file)
    else:
        token = None
    snapshot_download(
        repo_id=repo_id,
        repo_type=repo_type,
        revision=args.revision,
        allow_patterns=allow_patterns,
        local_dir=str(root),
        local_dir_use_symlinks=False,
        cache_dir=str(cache_dir),
        token=token,
        force_download=args.force,
        resume_download=True,
    )

    for p in paths:
        local_path = root / p
        if local_path.exists():
            print(f"OK: {p}")
        else:
            print(f"WARNING: missing after download: {p}")


if __name__ == "__main__":
    main()
