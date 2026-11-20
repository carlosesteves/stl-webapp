import pytest

from app.config import Settings


@pytest.mark.parametrize("raw", ["postgresql://u:p@h/db", "postgres://u:p@h/db"])
def test_postgres_urls_use_psycopg_driver(raw):
    assert Settings(database_url=raw).database_url == "postgresql+psycopg://u:p@h/db"


def test_explicit_driver_is_left_alone():
    url = "sqlite:///x.db"

    assert Settings(database_url=url).database_url == url
