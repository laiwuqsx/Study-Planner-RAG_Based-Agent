import json
import pathlib
import tempfile
import time
import urllib.request
import zipfile


BASE_URL = "http://127.0.0.1:8000"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def request_json(path: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict:
    headers = {}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def upload_document(path: pathlib.Path, course_id: int, token: str) -> dict:
    boundary = f"----StudyPlanner{int(time.time() * 1000)}"
    file_bytes = path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="material_type"\r\n\r\n',
        b"lecture_notes\r\n",
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode("utf-8"),
        f"Content-Type: {DOCX_CONTENT_TYPE}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    request = urllib.request.Request(
        f"{BASE_URL}/courses/{course_id}/documents",
        data=b"".join(parts),
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
    for _ in range(30):
        payload = request_json(f"/jobs/{job_id}", token=token)
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.8)
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
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Processes and Threads</w:t></w:r></w:p>
    <w:p><w:r><w:t>Threads share process memory while processes isolate address spaces and resources.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Synchronization</w:t></w:r></w:p>
    <w:p><w:r><w:t>Locks, semaphores, and condition variables coordinate access to shared state.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Virtual Memory</w:t></w:r></w:p>
    <w:p><w:r><w:t>Paging and translation isolate address spaces while supporting efficient memory management.</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)


def main() -> None:
    suffix = str(int(time.time()))
    auth = request_json("/auth/register", method="POST", payload={"username": f"phase8_{suffix}", "password": "pass123"})
    token = auth["access_token"]
    course = request_json(
        "/courses",
        method="POST",
        token=token,
        payload={"name": f"Review {suffix}", "term": "Spring 2026", "description": "Phase 8 smoke"},
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        docx_path = pathlib.Path(temp_dir) / "review.docx"
        write_sample_docx(docx_path)
        upload = upload_document(docx_path, course["id"], token)
        job = wait_for_job(upload["job"]["id"], token)
        topics = request_json(f"/courses/{course['id']}/topics", token=token)
        topic_id = topics["topics"][0]["id"]
        review = request_json(f"/courses/{course['id']}/topics/{topic_id}/review", token=token)
        refreshed_questions = request_json(
            f"/courses/{course['id']}/topics/{topic_id}/practice-questions",
            method="POST",
            token=token,
        )

    print(
        json.dumps(
            {
                "job_status": job["status"],
                "topic_count": len(topics["topics"]),
                "practice_question_count": len(review["practice_questions"]),
                "has_next_topic": review["next_topic"] is not None,
                "refreshed_question_count": len(refreshed_questions["questions"]),
                "first_question_kind": review["practice_questions"][0]["kind"] if review["practice_questions"] else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
