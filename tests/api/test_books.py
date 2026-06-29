from io import BytesIO
import zipfile
from decimal import Decimal

from app.models.book import BookStatus
from tests.conftest import FAKE_STORAGE
from tests.factories import (
    auth_headers,
    create_active_subscription,
    create_author,
    create_book,
    create_genre_tag,
    create_purchase,
    create_subscription_plan,
    create_user,
)


def _minimal_epub_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest>
    <item id="chap1" href="chapters/chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="chapters/chapter2.xhtml" media-type="application/xhtml+xml"/>
    <item id="img1" href="images/pic.png" media-type="image/png"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>
  </spine>
</package>""",
        )
        archive.writestr(
            "OEBPS/chapters/chapter1.xhtml",
            """<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Fallback title</title><script>alert(1)</script></head>
<body><h1 onclick="alert(1)">Chapter One</h1><img src="../images/pic.png"/></body>
</html>""",
        )
        archive.writestr(
            "OEBPS/chapters/chapter2.xhtml",
            """<html xmlns="http://www.w3.org/1999/xhtml"><body><h2>Chapter Two</h2></body></html>""",
        )
        archive.writestr("OEBPS/images/pic.png", b"PNG")
    return buffer.getvalue()


def _minimal_fb2_bytes() -> bytes:
    return b"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
  xmlns:l="http://www.w3.org/1999/xlink">
  <body>
    <section>
      <title><p>FB2 Chapter One</p></title>
      <p>Hello FB2</p>
      <image l:href="#cover.png"/>
    </section>
    <section>
      <title><p>FB2 Chapter Two</p></title>
      <p>Second chapter</p>
    </section>
  </body>
  <binary id="cover.png" content-type="image/png">UE5H</binary>
</FictionBook>"""


async def test_create_list_update_submit_and_delete_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")

    created = await client.post(
        "/books",
        headers=auth_headers(author),
        json={
            "title": "Draft Book",
            "description": "Draft description",
            "is_for_sale": True,
            "sale_price": "199.00",
        },
    )
    assert created.status_code == 201
    book_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    listed = await client.get("/books", params={"status": "draft", "q": "Draft"})
    assert listed.status_code == 200
    assert [book["id"] for book in listed.json()] == [book_id]

    updated = await client.patch(
        f"/books/{book_id}",
        headers=auth_headers(author),
        json={"title": "Updated Book"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Book"

    submitted = await client.post(f"/books/{book_id}/submit", headers=auth_headers(author))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending"

    deleted = await client.delete(f"/books/{book_id}", headers=auth_headers(author))
    assert deleted.status_code == 204


async def test_book_owner_guards_reject_other_users(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    response = await client.patch(
        f"/books/{book.id}",
        headers=auth_headers(reader),
        json={"title": "Stolen title"},
    )

    assert response.status_code == 403


async def test_book_upload_and_author_can_read_content(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    cover = await client.post(f"/books/{book.id}/cover", headers=auth_headers(author))
    assert cover.status_code == 200
    assert cover.json()["object_key"] == f"covers/{book.id}.jpg"

    confirm_cover = await client.patch(
        f"/books/{book.id}/cover-key",
        headers=auth_headers(author),
        params={"object_key": cover.json()["object_key"]},
    )
    assert confirm_cover.status_code == 200
    assert confirm_cover.json()["cover_key"] == cover.json()["object_key"]

    upload = await client.post(
        f"/books/{book.id}/file",
        headers=auth_headers(author),
        params={"file_format": "epub"},
    )
    assert upload.status_code == 200
    assert upload.json()["object_key"] == f"books/{book.id}.epub"

    confirm_file = await client.patch(
        f"/books/{book.id}/file-key",
        headers=auth_headers(author),
        params={
            "object_key": upload.json()["object_key"],
            "file_format": "epub",
            "file_size_bytes": 2048,
        },
    )
    assert confirm_file.status_code == 200

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(author))
    assert access.status_code == 200
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "author"

    content = await client.get(f"/books/{book.id}/content", headers=auth_headers(author))
    assert content.status_code == 200
    assert content.headers["content-disposition"] == "inline"
    assert len(content.content) > 0


async def test_content_rejects_reader_without_purchase_or_subscription(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=True,
        is_in_subscription=False,
        sale_price=Decimal("100.00"),
    )

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.status_code == 200
    assert access.json()["can_read"] is False
    assert access.json()["reason"] == "purchase_required"

    response = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert response.status_code == 403


async def test_content_allows_reader_with_purchase(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=True,
        is_in_subscription=False,
    )
    await create_purchase(db_session, user=reader, book=book)

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "purchased"

    content = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert content.status_code == 200


async def test_epub_file_key_processing_creates_reader_manifest_chapters_and_assets(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)
    object_key = f"books/{book.id}.epub"
    epub_bytes = _minimal_epub_bytes()
    FAKE_STORAGE[object_key] = epub_bytes

    confirmed = await client.patch(
        f"/books/{book.id}/file-key",
        headers=auth_headers(author),
        params={
            "object_key": object_key,
            "file_format": "epub",
            "file_size_bytes": len(epub_bytes),
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["reader_processing_status"] == "ready"
    assert confirmed.json()["reader_processing_error"] is None

    manifest = await client.get(f"/books/{book.id}/reader-manifest", headers=auth_headers(author))
    assert manifest.status_code == 200
    manifest_data = manifest.json()
    assert manifest_data["format"] == "epub"
    assert manifest_data["processing_status"] == "ready"
    assert [chapter["title"] for chapter in manifest_data["chapters"]] == ["Chapter One", "Chapter Two"]
    assert len(manifest_data["assets"]) == 1

    chapter_href = manifest_data["chapters"][0]["href"]
    chapter = await client.get(chapter_href, headers=auth_headers(author))
    assert chapter.status_code == 200
    chapter_data = chapter.json()
    assert chapter_data["index"] == 0
    assert "<script" not in chapter_data["html"]
    assert "onclick" not in chapter_data["html"]
    assert chapter_data["asset_ids"] == [manifest_data["assets"][0]["id"]]

    asset = await client.get(manifest_data["assets"][0]["href"], headers=auth_headers(author))
    assert asset.status_code == 200
    assert asset.headers["content-type"] == "image/png"
    assert asset.content == b"PNG"


async def test_fb2_file_key_processing_uses_reader_manifest_chapters_and_assets(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)
    object_key = f"books/{book.id}.fb2"
    fb2_bytes = _minimal_fb2_bytes()
    FAKE_STORAGE[object_key] = fb2_bytes

    confirmed = await client.patch(
        f"/books/{book.id}/file-key",
        headers=auth_headers(author),
        params={
            "object_key": object_key,
            "file_format": "fb2",
            "file_size_bytes": len(fb2_bytes),
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["file_format"] == "fb2"
    assert confirmed.json()["reader_processing_status"] == "ready"

    manifest = await client.get(f"/books/{book.id}/reader-manifest", headers=auth_headers(author))
    assert manifest.status_code == 200
    manifest_data = manifest.json()
    assert manifest_data["format"] == "fb2"
    assert [chapter["title"] for chapter in manifest_data["chapters"]] == [
        "FB2 Chapter One",
        "FB2 Chapter Two",
    ]
    assert len(manifest_data["assets"]) == 1

    chapter = await client.get(manifest_data["chapters"][0]["href"], headers=auth_headers(author))
    assert chapter.status_code == 200
    chapter_data = chapter.json()
    assert chapter_data["content_type"] == "html"
    assert "<p>Hello FB2</p>" in chapter_data["html"]
    assert chapter_data["asset_ids"] == [manifest_data["assets"][0]["id"]]

    asset = await client.get(manifest_data["assets"][0]["href"], headers=auth_headers(author))
    assert asset.status_code == 200
    assert asset.headers["content-type"] == "image/png"
    assert asset.content == b"PNG"


async def test_content_chunk_returns_range(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    chunk = await client.get(
        f"/books/{book.id}/content/chunk",
        headers=auth_headers(author),
        params={"offset": 0, "size": 1024},
    )
    assert chunk.status_code == 200
    assert chunk.headers["content-range"].startswith("bytes 0-")
    assert len(chunk.content) == 1024


async def test_content_supports_http_range_for_pdf(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)
    book.file_format = "pdf"
    await db_session.commit()

    response = await client.get(
        f"/books/{book.id}/content",
        headers={**auth_headers(author), "Range": "bytes=5-14"},
    )

    assert response.status_code == 206
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == "bytes 5-14/10400"
    assert response.headers["content-length"] == "10"
    assert response.content == b"CONTENT-BO"


async def test_content_supports_open_ended_http_range(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)
    book.file_format = "pdf"
    await db_session.commit()

    response = await client.get(
        f"/books/{book.id}/content",
        headers={**auth_headers(author), "Range": "bytes=10393-"},
    )

    assert response.status_code == 206
    assert response.headers["content-range"] == "bytes 10393-10399/10400"
    assert response.content == b"ONTENT-"


async def test_content_rejects_unsatisfiable_http_range(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.published)

    response = await client.get(
        f"/books/{book.id}/content",
        headers={**auth_headers(author), "Range": "bytes=999999-1000000"},
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */10400"


async def test_content_rejects_unpublished_book_for_non_author(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    response = await client.get(f"/books/{book.id}/content", headers=auth_headers(reader))
    assert response.status_code == 403


async def test_subscription_reader_can_read_in_subscription_book(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=reader, plan=plan)
    book = await create_book(
        db_session,
        author=author,
        status=BookStatus.published,
        is_for_sale=False,
        is_in_subscription=True,
    )

    access = await client.get(f"/books/{book.id}/access", headers=auth_headers(reader))
    assert access.json()["can_read"] is True
    assert access.json()["reason"] == "subscription"


async def test_recommendations_returns_new_and_popular(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    await create_book(db_session, author=author, title="Book A")
    await create_book(db_session, author=author, title="Book B")

    response = await client.get("/books/recommendations", params={"limit": 5})
    assert response.status_code == 200
    data = response.json()
    assert "new" in data and "popular" in data
    assert len(data["new"]) >= 1


async def test_genre_tags_can_be_created_listed_and_attached(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author, status=BookStatus.draft)

    created = await client.post(
        "/books/genre-tags",
        headers=auth_headers(author),
        json={"name": "Fantasy"},
    )
    assert created.status_code == 201
    tag_id = created.json()["id"]

    duplicate = await client.post(
        "/books/genre-tags",
        headers=auth_headers(author),
        json={"name": "Fantasy"},
    )
    assert duplicate.status_code == 409

    listed = await client.get("/books/genre-tags/all")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Fantasy"

    genres = await client.get("/books/genres")
    assert genres.status_code == 200
    assert genres.json() == listed.json()

    attached = await client.put(
        f"/books/{book.id}/genre-tags",
        headers=auth_headers(author),
        json={"genre_tag_ids": [tag_id]},
    )
    assert attached.status_code == 200
    assert attached.json()[0]["id"] == tag_id

    book_tags = await client.get(f"/books/{book.id}/genre-tags")
    assert book_tags.status_code == 200
    assert book_tags.json()[0]["name"] == "Fantasy"


async def test_book_user_tags_are_unique_per_user(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    book = await create_book(db_session, author=author)

    added = await client.post(
        f"/books/{book.id}/user-tags",
        headers=auth_headers(reader),
        json={"name": "Cozy"},
    )
    assert added.status_code == 201
    tag_id = added.json()["id"]

    duplicate = await client.post(
        f"/books/{book.id}/user-tags",
        headers=auth_headers(reader),
        json={"name": "Cozy"},
    )
    assert duplicate.status_code == 409

    listed = await client.get(f"/books/{book.id}/user-tags")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Cozy"

    removed = await client.delete(
        f"/books/{book.id}/user-tags/{tag_id}",
        headers=auth_headers(reader),
    )
    assert removed.status_code == 204


async def test_set_book_genre_tags_returns_404_for_unknown_tag(client, db_session):
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)
    tag = await create_genre_tag(db_session, name="Unused")
    await db_session.delete(tag)
    await db_session.commit()

    response = await client.put(
        f"/books/{book.id}/genre-tags",
        headers=auth_headers(author),
        json={"genre_tag_ids": [str(tag.id)]},
    )

    assert response.status_code == 404
