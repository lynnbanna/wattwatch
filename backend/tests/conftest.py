import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import get_session
from app.main import app
from app.models import Base


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Every test gets an empty in-memory database and its own upload directory."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)

    def session_override():
        session = make_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    yield make_session
    app.dependency_overrides.pop(get_session, None)
    engine.dispose()
