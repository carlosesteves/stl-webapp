from app.models import Item


def test_item_is_unpublished_by_default(session):
    item = Item(name="Widget", description="A thing")
    session.add(item)
    session.commit()

    saved = session.get(Item, item.id)

    assert saved.name == "Widget"
    assert saved.description == "A thing"
    assert saved.published is False
