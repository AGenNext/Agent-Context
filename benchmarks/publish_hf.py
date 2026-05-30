"""One-command HuggingFace publish for AgentKube-ContextGov-v0.

Usage:
    HF_TOKEN=<your-token> python3 benchmarks/publish_hf.py

Creates (or updates) the dataset repo AGenNext/AgentKube-ContextGov-v0
and uploads benchmarks/hf_dataset/ as the dataset root.

The repo name and org are configurable via env vars — no hardcoded values:
    HF_REPO   — default: AGenNext/AgentKube-ContextGov-v0
    HF_TOKEN  — required
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HF_REPO = os.environ.get("HF_REPO", "AGenNext/AgentKube-ContextGov-v0")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not HF_TOKEN:
    print("error: HF_TOKEN env var is required", file=sys.stderr)
    sys.exit(1)

try:
    from huggingface_hub import HfApi
except ImportError:
    print("error: pip install huggingface_hub", file=sys.stderr)
    sys.exit(1)

api = HfApi(token=HF_TOKEN)

local_dir = Path(__file__).parent / "hf_dataset"

print(f"Creating/checking dataset repo: {HF_REPO}")
api.create_repo(repo_id=HF_REPO, repo_type="dataset", exist_ok=True)

print(f"Uploading {local_dir} → {HF_REPO}")
api.upload_folder(
    folder_path=str(local_dir),
    repo_id=HF_REPO,
    repo_type="dataset",
    commit_message="AgentKube-ContextGov-v0 dataset upload",
)

print(f"Done: https://huggingface.co/datasets/{HF_REPO}")
