#!/usr/bin/env python3
"""E2E: register author → create book → upload file → publish → verify catalog."""

from __future__ import annotations

import sys
import uuid

import httpx

BASE = "https://team16.st.ifbest.org/api"


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"e2e-author-{suffix}@example.com"
    username = f"e2eauthor{suffix}"
    password = "password123"

    with httpx.Client(base_url=BASE, timeout=60.0, verify=True) as client:
        r = client.post(
            "/auth/register",
            json={
                "email": email,
                "username": username,
                "password": password,
                "role": "author",
            },
        )
        print(f"register: {r.status_code}")
        if r.status_code != 201:
            return 1

        r = client.post("/auth/login", json={"email": email, "password": password})
        print(f"login: {r.status_code}")
        if r.status_code != 200:
            return 1

        r = client.get("/books/genre-tags/all")
        genres = r.json()
        print(f"genres: {r.status_code} ({len(genres)} tags)")
        if not genres:
            print("No genre tags", file=sys.stderr)
            return 1
        genre_id = genres[0]["id"]

        r = client.post(
            "/books",
            json={
                "title": f"E2E Book {suffix}",
                "description": "Automated test",
                "is_in_subscription": True,
                "is_for_sale": True,
                "sale_price": "9.99",
            },
        )
        print(f"create_book: {r.status_code}")
        if r.status_code != 201:
            return 1
        book_id = r.json()["id"]

        r = client.post(f"/books/{book_id}/file", params={"file_format": "pdf"})
        print(f"file_upload_url: {r.status_code}")
        if r.status_code != 200:
            return 1
        upload = r.json()

        pdf_bytes = b"%PDF-1.4 e2e test content"
        with httpx.Client(timeout=60.0, verify=True) as upload_client:
            put = upload_client.put(
                upload["upload_url"],
                content=pdf_bytes,
                headers={"Content-Type": "application/pdf"},
            )
        print(f"file_put: {put.status_code}")

        r = client.patch(
            f"/books/{book_id}/file-key",
            params={
                "object_key": upload["object_key"],
                "file_format": "pdf",
                "file_size_bytes": len(pdf_bytes),
            },
        )
        print(f"file_key_confirm: {r.status_code}")
        if r.status_code != 200:
            return 1

        r = client.put(
            f"/books/{book_id}/genre-tags",
            json={"genre_tag_ids": [genre_id]},
        )
        print(f"genre_tags: {r.status_code}")

        r = client.post(f"/books/{book_id}/publish")
        print(f"publish: {r.status_code}")
        if r.status_code != 200:
            return 1

        r = client.get("/books", params={"offset": 0, "limit": 20})
        books = r.json()
        print(f"catalog: {r.status_code} ({len(books)} books)")
        if not any(b.get("id") == book_id for b in books):
            print("Published book not in catalog", file=sys.stderr)
            return 1

    print("E2E OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
