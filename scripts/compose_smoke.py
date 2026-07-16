#!/usr/bin/env python3
"""Compose smoke: health → ingest fixture → wait INDEXED → chat completions."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "_test_upload.txt"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-url", default="http://localhost:8080")
    parser.add_argument("--agent-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    with httpx.Client(timeout=30) as client:
        for name, url in (
            ("document-index", f"{args.index_url}/health"),
            ("query-agent", f"{args.agent_url}/health"),
        ):
            r = client.get(url)
            r.raise_for_status()
            print(f"ok {name}")

        if not FIXTURE.exists():
            FIXTURE.write_text("Revenue grew 20% in Q3.\n", encoding="utf-8")

        with FIXTURE.open("rb") as f:
            r = client.post(
                f"{args.index_url}/ingest",
                files={"file": ("smoke.txt", f, "text/plain")},
            )
        if r.status_code == 409:
            docs = client.get(f"{args.index_url}/documents", params={"status": "INDEXED"}).json()
            match = next((d for d in docs if d.get("name") == "smoke.txt"), None)
            if not match:
                print("duplicate ingest but smoke.txt not listed:", r.text)
                return 1
            doc_id = match["document_id"]
            print(f"reusing indexed {doc_id}")
        else:
            r.raise_for_status()
            doc_id = r.json()["document_id"]
            print(f"ingested {doc_id}")

        deadline = time.time() + args.timeout
        while time.time() < deadline:
            st = client.get(f"{args.index_url}/documents/{doc_id}")
            st.raise_for_status()
            status = st.json()["status"]
            if status == "INDEXED":
                break
            if status == "FAILED":
                print("ingest failed", st.json())
                return 1
            time.sleep(2)
        else:
            print("timeout waiting for INDEXED")
            return 1

        chat = client.post(
            f"{args.agent_url}/v1/chat/completions",
            json={
                "model": "file-qa-agent",
                "messages": [{"role": "user", "content": "What was revenue growth?"}],
                "stream": False,
            },
        )
        chat.raise_for_status()
        body = chat.json()
        content = body["choices"][0]["message"]["content"]
        reasoning = body["choices"][0]["message"].get("reasoning_content", "")
        print("answer:", content[:200])
        print("reasoning:", reasoning)
        if "grounded=True" not in reasoning and "hits=0" in reasoning:
            print("warning: ungrounded or empty hits")
        return 0


if __name__ == "__main__":
    sys.exit(main())
