"""Additive legacy-column upgrades.

New tables are added by create_all immediately
after this function. Existing tables and records are never rebuilt or deleted.
"""

from sqlalchemy import inspect


def migrate(connection) -> None:
    inspector = inspect(connection)
    for table, names in {
        "tracks": ("display_artist", "display_title"),
        "track_tags": ("display_name",),
    }.items():
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name in names:
            if name not in existing:
                # Identifiers are fixed above, never taken from users or providers.
                connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" VARCHAR')
    if inspector.has_table("recommendation_history"):
        existing = {column["name"] for column in inspector.get_columns("recommendation_history")}
        for name, sql_type in {"ranking_score": "FLOAT", "batch_id": "VARCHAR", "position": "INTEGER"}.items():
            if name not in existing:
                connection.exec_driver_sql(f'ALTER TABLE recommendation_history ADD COLUMN "{name}" {sql_type}')
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendation_batch_track "
            "ON recommendation_history (user_id, batch_id, track_id)")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_recommendation_user_time "
            "ON recommendation_history (user_id, recommended_at)")
    if inspector.has_table("track_tags"):
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_track_tags_name_track ON track_tags (name, track_id)")
