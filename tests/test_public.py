from app.models import Organization


def test_home_lists_only_published_organizations(client, session):
    session.add_all([
        Organization(name="Visible", is_published=True),
        Organization(name="Hidden", is_published=False),
    ])
    session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert "Visible" in response.text
    assert "Hidden" not in response.text
