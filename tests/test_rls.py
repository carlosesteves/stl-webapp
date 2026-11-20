from types import SimpleNamespace

from app.rls import enable_row_level_security


class RecordingConnection:
    def __init__(self, dialect_name):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))


def test_enables_rls_on_owned_public_tables_on_postgres():
    connection = RecordingConnection("postgresql")

    enable_row_level_security(connection)

    (sql,) = connection.statements
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "schemaname = 'public'" in sql
    assert "tableowner = current_user" in sql


def test_does_nothing_on_other_databases():
    connection = RecordingConnection("sqlite")

    enable_row_level_security(connection)

    assert connection.statements == []
