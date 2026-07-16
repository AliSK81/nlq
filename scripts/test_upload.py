"""End-to-end upload test against document-index REST API."""
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:8080"


def multipart_pdf(path: Path) -> bytes:
    boundary = b"----NlqTestBoundary"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + path.name.encode() + b'"\r\n'
        b"Content-Type: application/pdf\r\n\r\n"
    )
    body += path.read_bytes()
    body += b"\r\n--" + boundary + b"--\r\n"
    return body


def main() -> int:
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not pdf or not pdf.exists():
        # minimal valid-enough payload for ingest path test
        tmp = Path("_test_upload.txt")
        tmp.write_text("hello nlq upload test", encoding="utf-8")
        pdf = tmp

    req = urllib.request.Request(
        f"{BASE}/ingest",
        data=multipart_pdf(pdf),
        headers={"Content-Type": "multipart/form-data; boundary=----NlqTestBoundary"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        data = json.load(resp)
    print("ingest", resp.status, data)
    doc_id = data["document_id"]

    for _ in range(30):
        detail = json.load(urllib.request.urlopen(f"{BASE}/documents/{doc_id}", timeout=10))
        print("status", detail["status"])
        if detail["status"] in ("INDEXED", "FAILED"):
            print("final", detail)
            return 0 if detail["status"] == "INDEXED" else 1
        time.sleep(2)
    print("timeout waiting for INDEXED")
    return 1


if __name__ == "__main__":
    import json

    raise SystemExit(main())
