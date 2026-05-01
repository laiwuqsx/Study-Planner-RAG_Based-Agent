import json
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


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


def main() -> None:
    suffix = str(int(time.time()))

    owner = request_json(
        "/auth/register",
        method="POST",
        payload={"username": f"owner_{suffix}", "password": "pass123"},
    )
    course = request_json(
        "/courses",
        method="POST",
        token=owner["access_token"],
        payload={
            "name": f"Private Course {suffix}",
            "term": "Spring 2026",
            "description": "Owner-only course",
        },
    )

    other = request_json(
        "/auth/register",
        method="POST",
        payload={"username": f"other_{suffix}", "password": "pass123"},
    )
    other_courses = request_json("/courses", token=other["access_token"])

    cross_user_blocked = False
    try:
        request_json(f"/courses/{course['id']}", token=other["access_token"])
    except urllib.error.HTTPError as exc:
        cross_user_blocked = exc.code == 404

    print(
        json.dumps(
            {
                "owner_course_id": course["id"],
                "other_course_count": len(other_courses["courses"]),
                "cross_user_blocked": cross_user_blocked,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

