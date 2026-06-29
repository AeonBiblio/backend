import pytest

from app.core.storage import with_public_path_prefix


@pytest.fixture
def storage_prefix(monkeypatch):
    monkeypatch.setattr("app.core.storage.settings.minio_public_path_prefix", "/storage")


def test_with_public_path_prefix_inserts_storage_prefix(storage_prefix):
    url = "https://team16.st.ifbest.org/aeonbiblio/covers/book.jpg?X-Amz-Signature=abc"

    result = with_public_path_prefix(url)

    assert (
        result
        == "https://team16.st.ifbest.org/storage/aeonbiblio/covers/book.jpg?X-Amz-Signature=abc"
    )


def test_with_public_path_prefix_is_idempotent(storage_prefix):
    url = "https://team16.st.ifbest.org/storage/aeonbiblio/covers/book.jpg?sig=1"

    assert with_public_path_prefix(url) == url


def test_with_public_path_prefix_without_prefix_returns_original(monkeypatch):
    monkeypatch.setattr("app.core.storage.settings.minio_public_path_prefix", "")

    url = "http://localhost:9000/aeonbiblio/covers/book.jpg?sig=1"

    assert with_public_path_prefix(url) == url
