from app.models import Item


def test_home_lists_only_published_items(client, session):
    session.add_all([
        Item(name="Visible", published=True),
        Item(name="Hidden", published=False),
    ])
    session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert "Visible" in response.text
    assert "Hidden" not in response.text
