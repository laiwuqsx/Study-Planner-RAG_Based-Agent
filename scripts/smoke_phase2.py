import json
import pathlib
import tempfile
import time
import urllib.error
import urllib.request


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

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def upload_document(path: pathlib.Path, course_id: int, token: str) -> dict:
    boundary = f"----StudyPlanner{int(time.time() * 1000)}"
    file_bytes = path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="material_type"\r\n\r\n',
        b"course_notes\r\n",
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode("utf-8"),
        f"Content-Type: {DOCX_CONTENT_TYPE}\r\n\r\n".encode("utf-8"),
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
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    suffix = str(int(time.time()))
    owner = request_json(
        "/auth/register",
        method="POST",
        payload={"username": f"phase2_{suffix}", "password": "pass123"},
    )
    course = request_json(
        "/courses",
        method="POST",
        token=owner["access_token"],
        payload={"name": f"Uploads {suffix}", "term": "Spring 2026", "description": "Upload test"},
    )

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        handle.write(b"phase 2 upload placeholder")
        temp_path = pathlib.Path(handle.name)

    try:
        upload_payload = upload_document(temp_path, course["id"], owner["access_token"])
        job_id = upload_payload["job"]["id"]

        final_job = upload_payload["job"]
        for _ in range(12):
            final_job = request_json(f"/jobs/{job_id}", token=owner["access_token"])
            if final_job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.8)

        documents = request_json(f"/courses/{course['id']}/documents", token=owner["access_token"])

        outsider = request_json(
            "/auth/register",
            method="POST",
            payload={"username": f"phase2_other_{suffix}", "password": "pass123"},
        )
        blocked = False
        try:
            request_json(f"/jobs/{job_id}", token=outsider["access_token"])
        except urllib.error.HTTPError as exc:
            blocked = exc.code == 404

        print(
            json.dumps(
                {
                    "document_count": len(documents["documents"]),
                    "job_status": final_job["status"],
                    "document_status": documents["documents"][0]["status"] if documents["documents"] else None,
                    "cross_user_job_blocked": blocked,
                },
                ensure_ascii=False,
            )
        )
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
