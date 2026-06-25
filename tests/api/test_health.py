from app.models.book import BookStatus
from tests.factories import auth_headers, create_book, create_user


async def test_health_returns_ok_with_db(client):
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] is True
