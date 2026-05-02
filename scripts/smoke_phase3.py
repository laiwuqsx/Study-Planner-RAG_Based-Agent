import json
import pathlib
import tempfile
import time
import urllib.request
import zipfile


BASE_URL = "http://127.0.0.1:8000"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_CONTENT_TYPE = "application/pdf"


def request_json(path: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    headers = {}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def upload_document(path: pathlib.Path, course_id: int, token: str, content_type: str) -> dict:
    boundary = f"----StudyPlanner{int(time.time() * 1000)}"
    file_bytes = path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="material_type"\r\n\r\n',
        b"course_notes\r\n",
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)
    request = urllib.request.Request(
        f"{BASE_URL}/courses/{course_id}/documents",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def wait_for_job(job_id: int, token: str) -> dict:
    payload = {}
    for _ in range(20):
        payload = request_json(f"/jobs/{job_id}", token=token)
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.6)
    return payload


def write_sample_docx(path: pathlib.Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
</w:styles>"""
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Dynamic Programming</w:t></w:r></w:p>
    <w:p><w:r><w:t>Dynamic programming solves overlapping subproblems with memoization and tabulation.</w:t></w:r></w:p>
    <w:p><w:r><w:t>State transitions and recurrence relations define the solution.</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)


def write_sample_pdf(path: pathlib.Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length 88 >>\nstream\nBT\n/F1 18 Tf\n72 720 Td\n(Dynamic Programming) Tj\n0 -24 Td\n(Recurrence and memoization) Tj\nET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("utf-8"))
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")
    xref_start = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    buffer.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode("utf-8")
    )
    path.write_bytes(buffer)


def main() -> None:
    suffix = str(int(time.time()))
    auth = request_json("/auth/register", method="POST", payload={"username": f"phase3_{suffix}", "password": "pass123"})
    token = auth["access_token"]
    course = request_json(
        "/courses",
        method="POST",
        token=token,
        payload={"name": f"Parsing {suffix}", "term": "Spring 2026", "description": "Phase 3 smoke"},
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        docx_path = temp_path / "sample.docx"
        pdf_path = temp_path / "sample.pdf"
        write_sample_docx(docx_path)
        write_sample_pdf(pdf_path)

        docx_upload = upload_document(docx_path, course["id"], token, DOCX_CONTENT_TYPE)
        pdf_upload = upload_document(pdf_path, course["id"], token, PDF_CONTENT_TYPE)

        docx_job = wait_for_job(docx_upload["job"]["id"], token)
        pdf_job = wait_for_job(pdf_upload["job"]["id"], token)

        docx_chunks = request_json(
            f"/courses/{course['id']}/documents/{docx_upload['document']['id']}/chunks",
            token=token,
        )
        pdf_chunks = request_json(
            f"/courses/{course['id']}/documents/{pdf_upload['document']['id']}/chunks",
            token=token,
        )
        documents = request_json(f"/courses/{course['id']}/documents", token=token)

    print(
        json.dumps(
            {
                "docx_status": docx_job["status"],
                "pdf_status": pdf_job["status"],
                "docx_parent_chunks": len(docx_chunks["parent_chunks"]),
                "docx_child_chunks": len(docx_chunks["child_chunks"]),
                "pdf_parent_chunks": len(pdf_chunks["parent_chunks"]),
                "pdf_child_chunks": len(pdf_chunks["child_chunks"]),
                "document_count": len(documents["documents"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
