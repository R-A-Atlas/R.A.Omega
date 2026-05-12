"""Database architect helper."""

from __future__ import annotations


def create_table_sql(table: str, columns: dict[str, str]) -> str:
    cols = ", ".join(f"{name} {kind}" for name, kind in columns.items())
    return f"CREATE TABLE IF NOT EXISTS {table} ({cols});"
