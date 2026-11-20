from sqlalchemy import text

ENABLE_RLS_SQL = text(
    """
    DO $$
    DECLARE t record;
    BEGIN
      FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tableowner = current_user
      LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(t.tablename) || ' ENABLE ROW LEVEL SECURITY';
      END LOOP;
    END $$;
    """
)


def enable_row_level_security(connection) -> None:
    """Turn on RLS (with no policies) for every table we own in the public schema.

    Supabase exposes public tables through its REST API; with RLS on and no
    policies, that API sees nothing. The app connects as the table owner, which
    is exempt from RLS. Idempotent, so it covers tables added by later migrations.
    """
    if connection.dialect.name == "postgresql":
        connection.execute(ENABLE_RLS_SQL)
