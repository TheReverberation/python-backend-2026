from uuid import uuid4

import pytest
from sqlalchemy import text
from storage.database import Base, SessionLocal, engine


@pytest.fixture(scope="session", autouse=True)
def database():
    schema = "test_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = engine.execution_options(schema_translate_map={None: schema})
    SessionLocal.configure(bind=test_engine)
    Base.metadata.create_all(test_engine)
    try:
        yield
    finally:
        SessionLocal.configure(bind=engine)
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
