from tests.factories import auth_headers, create_author, create_book, create_user


def _progress_payload(updated_at: str, *, page_index: int = 12) -> dict:
    return {
        "chapter_id": "chapter-1",
        "chapter_index": 0,
        "chapter_offset": 0,
        "page_index": page_index,
        "page_count": 48,
        "percentage": 25.53,
        "cfi": None,
        "settings_hash": "serif:20:1.7:36:56:2",
        "updated_at": updated_at,
    }


def _settings_payload(updated_at: str, *, theme: str = "light") -> dict:
    return {
        "theme": theme,
        "font_family": "var(--font-serif)",
        "font_size": 20,
        "line_height": 1.7,
        "page_mode": "paginated",
        "text_align": "left",
        "margin": 36,
        "column_gap": 56,
        "columns_per_page": 2,
        "enable_keyboard_arrows": True,
        "enable_keyboard_letters": True,
        "enable_reader_arrows": True,
        "enable_wheel_navigation": True,
        "limit_wheel_to_one_page": True,
        "updated_at": updated_at,
    }


def _annotation_payload(annotation_id: str, updated_at: str, *, page_index: int = 12) -> dict:
    return {
        "id": annotation_id,
        "chapter_id": "chapter-1",
        "chapter_index": 0,
        "type": "bookmark",
        "page_index": page_index,
        "page_number": None,
        "page_count": 48,
        "percentage": 25.53,
        "settings_hash": "serif:20:1.7:36:56:2",
        "range": None,
        "quote": None,
        "color": None,
        "text": None,
        "note": None,
        "created_at": "2026-07-02T12:00:00.000Z",
        "updated_at": updated_at,
        "deleted_at": None,
    }


async def test_reader_progress_uses_last_write_wins(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)

    created = await client.put(
        f"/books/{book.id}/reader/progress",
        headers={**auth_headers(reader), "Idempotency-Key": "progress-1"},
        json=_progress_payload("2026-07-02T12:00:00.000Z", page_index=12),
    )
    assert created.status_code == 204

    stale = await client.put(
        f"/books/{book.id}/reader/progress",
        headers={**auth_headers(reader), "Idempotency-Key": "progress-stale"},
        json=_progress_payload("2026-07-02T11:00:00.000Z", page_index=1),
    )
    assert stale.status_code == 204

    current = await client.get(f"/books/{book.id}/reader/progress", headers=auth_headers(reader))
    assert current.status_code == 200
    assert current.json()["page_index"] == 12

    newer = await client.put(
        f"/books/{book.id}/reader/progress",
        headers={**auth_headers(reader), "Idempotency-Key": "progress-2"},
        json=_progress_payload("2026-07-02T13:00:00.000Z", page_index=18),
    )
    assert newer.status_code == 204

    updated = await client.get(f"/books/{book.id}/reader/progress", headers=auth_headers(reader))
    assert updated.json()["page_index"] == 18


async def test_reader_settings_can_be_saved_and_loaded(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)

    response = await client.put(
        f"/books/{book.id}/reader/settings",
        headers=auth_headers(reader),
        json=_settings_payload("2026-07-02T12:00:00.000Z", theme="sepia"),
    )
    assert response.status_code == 204

    loaded = await client.get(f"/books/{book.id}/reader/settings", headers=auth_headers(reader))
    assert loaded.status_code == 200
    assert loaded.json()["theme"] == "sepia"
    assert loaded.json()["columns_per_page"] == 2


async def test_reader_annotations_upsert_list_and_tombstone(client, db_session):
    reader = await create_user(db_session, email="reader@example.com", username="reader")
    author = await create_author(db_session, email="author@example.com", username="author")
    book = await create_book(db_session, author=author)
    annotation_id = f"bookmark:{reader.id}:{book.id}:chapter-1:12:settings"

    created = await client.put(
        f"/books/{book.id}/reader/annotations/{annotation_id}",
        headers=auth_headers(reader),
        json=_annotation_payload(annotation_id, "2026-07-02T12:00:00.000Z"),
    )
    assert created.status_code == 204

    listed = await client.get(f"/books/{book.id}/reader/annotations", headers=auth_headers(reader))
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == annotation_id

    mismatch = await client.put(
        f"/books/{book.id}/reader/annotations/{annotation_id}",
        headers=auth_headers(reader),
        json=_annotation_payload("other-id", "2026-07-02T13:00:00.000Z"),
    )
    assert mismatch.status_code == 400

    deleted = await client.delete(
        f"/books/{book.id}/reader/annotations/{annotation_id}?updated_at=2026-07-02T14:00:00.000Z",
        headers=auth_headers(reader),
    )
    assert deleted.status_code == 204

    active = await client.get(f"/books/{book.id}/reader/annotations", headers=auth_headers(reader))
    assert active.status_code == 200
    assert active.json() == []

    with_deleted = await client.get(
        f"/books/{book.id}/reader/annotations?include_deleted=true",
        headers=auth_headers(reader),
    )
    assert with_deleted.status_code == 200
    assert with_deleted.json()[0]["deleted_at"] is not None
