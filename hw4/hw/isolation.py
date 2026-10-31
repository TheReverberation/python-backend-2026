from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from storage.database import engine


def scalar(connection, sql):
    return connection.execute(text(sql)).scalar_one()


def reset(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE accounts"))
        conn.execute(text("INSERT INTO accounts VALUES (1, 100), (2, 100)"))


def reads(engine, kind, level):
    reset(engine)
    with engine.connect().execution_options(isolation_level=level) as a, engine.connect() as b:
        sql = "SELECT balance FROM accounts WHERE id = 1"
        if kind == "phantom read":
            sql = "SELECT count(*) FROM accounts WHERE balance >= 100"
        first = scalar(a, sql)
        if kind == "phantom read":
            b.execute(text("INSERT INTO accounts VALUES (3, 100)"))
        else:
            b.execute(text("UPDATE accounts SET balance = 50 WHERE id = 1"))
        if kind != "dirty read":
            b.commit()
        second = scalar(a, sql)
        expected = kind != "dirty read" and level == "READ COMMITTED"
        assert (first != second) == expected, (kind, level, first, second)
        print(f"{kind}, {level}: A: {first} -> {second}; аномалия: {expected}")


def serialization(engine, level):
    reset(engine)
    rejected = False
    with (
        engine.connect().execution_options(isolation_level=level) as a,
        engine.connect().execution_options(isolation_level=level) as b,
    ):
        assert scalar(a, "SELECT sum(balance) FROM accounts") == 200
        assert scalar(b, "SELECT sum(balance) FROM accounts") == 200
        try:
            a.execute(text("UPDATE accounts SET balance = balance - 150 WHERE id = 1"))
            b.execute(text("UPDATE accounts SET balance = balance - 150 WHERE id = 2"))
            a.commit()
            b.commit()
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) != "40001":
                raise
            rejected = True
            a.rollback()
            b.rollback()
    with engine.connect() as conn:
        total = scalar(conn, "SELECT sum(balance) FROM accounts")
    assert rejected == (level == "SERIALIZABLE")
    assert (total < 0) == (level == "REPEATABLE READ")
    print(f"write skew, {level}: сумма={total}, SerializationFailure={rejected}")


def main():
    schema = "isolation_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    
    demo_engine = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with demo_engine.begin() as conn:
            conn.execute(
                text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL)")
            )
        for level in ("READ UNCOMMITTED", "READ COMMITTED"):
            reads(demo_engine, "dirty read", level)
        for level in ("READ COMMITTED", "REPEATABLE READ"):
            reads(demo_engine, "non-repeatable read", level)
        for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            reads(demo_engine, "phantom read", level)
        for level in ("REPEATABLE READ", "SERIALIZABLE"):
            serialization(demo_engine, level)
    finally:
        demo_engine.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
