from sqlalchemy import inspect, text


def ensure_draft_status_column(engine):
    """Add tracker status to existing installations; create_all handles fresh databases."""
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("drafts")}
        if "status" not in columns:
            optional = "IF NOT EXISTS " if connection.dialect.name == "postgresql" else ""
            connection.execute(text(f"ALTER TABLE drafts ADD COLUMN {optional}status VARCHAR NOT NULL DEFAULT 'Draft'"))
