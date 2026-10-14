from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.models import Base

BACKEND = Path(__file__).resolve().parents[1]


def test_migrations_create_the_tables_the_models_expect(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(config, "head")

    inspector = inspect(create_engine(url))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"]: c["nullable"] for c in inspector.get_columns(table.name)}
        expected = {c.name: c.nullable for c in table.columns}
        assert migrated == expected, table.name

    command.downgrade(config, "base")
    assert "analyses" not in inspect(create_engine(url)).get_table_names()
