import json

from eval_common import parse_common_args, request_json, resolve_token, write_output


def main() -> None:
    parser = parse_common_args("Dump all document chunks for one course to help benchmark annotation.", include_benchmark=False)
    parser.add_argument("--course-id", type=int, required=True, help="Target course ID.")
    args = parser.parse_args()

    token = resolve_token(base_url=args.base_url, token=args.token, username=args.username, password=args.password)
    documents_payload = request_json(
        base_url=args.base_url,
        path=f"/courses/{args.course_id}/documents",
        token=token,
    )
    documents = documents_payload.get("documents", [])
    dump_documents: list[dict] = []
    for document in documents:
        chunks = request_json(
            base_url=args.base_url,
            path=f"/courses/{args.course_id}/documents/{document['id']}/chunks",
            token=token,
        )
        dump_documents.append(
            {
                "document": {
                    "id": document["id"],
                    "filename": document["filename"],
                    "material_type": document["material_type"],
                    "chunk_count": document["chunk_count"],
                },
                "parent_chunks": chunks.get("parent_chunks", []),
                "child_chunks": chunks.get("child_chunks", []),
            }
        )

    payload = {
        "course_id": args.course_id,
        "document_count": len(dump_documents),
        "documents": dump_documents,
    }
    write_output(args.output, payload)


if __name__ == "__main__":
    main()
