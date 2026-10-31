from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shop_api.main import app
from sqlalchemy import text
from storage import database as db


@contextmanager
def temporary_database():
    original_engine = db.engine
    original_bind = db.SessionLocal.kw["bind"]
    schema = "test_" + uuid4().hex
    with original_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = original_engine.execution_options(schema_translate_map={None: schema})
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(db, "engine", test_engine)
            db.SessionLocal.configure(bind=test_engine)
            db.init_db()
            yield
    finally:
        db.SessionLocal.configure(bind=original_bind)
        with original_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture(scope="session", autouse=True)
def database():
    with temporary_database():
        yield


@pytest.fixture
def isolated_client(database):
    with temporary_database(), TestClient(app) as client:
        yield client
