"""One-time LongMemEval-S download (~278 MB) from HuggingFace.

    python scripts/download_longmemeval.py

The file lands in data/longmemeval_s/ (gitignored).
"""

from __future__ import annotations

from gaucho_agent.services import longmemeval


def main() -> int:
    if longmemeval.is_available():
        print(f"already present: {longmemeval.DEFAULT_PATH}")
        return 0
    print(f"downloading {longmemeval.HF_REPO}:{longmemeval.HF_FILE} ...")
    path = longmemeval.download()
    import os

    print(f"saved {path} ({os.path.getsize(path):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
