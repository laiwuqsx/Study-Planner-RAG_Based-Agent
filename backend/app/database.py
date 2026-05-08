from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def init_db() -> None:
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "topics" not in inspector.get_table_names():
        return

    timestamp_type = "TIMESTAMP" if engine.dialect.name == "postgresql" else "DATETIME"
    topic_columns = {column["name"] for column in inspector.get_columns("topics")}
    statements: list[str] = []
    if "status" not in topic_columns:
        statements.append("ALTER TABLE topics ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
    if "quality_score" not in topic_columns:
        statements.append("ALTER TABLE topics ADD COLUMN quality_score INTEGER NOT NULL DEFAULT 3")
    if "review_note" not in topic_columns:
        statements.append("ALTER TABLE topics ADD COLUMN review_note TEXT NOT NULL DEFAULT ''")
    if "mastery_status" not in topic_columns:
        statements.append("ALTER TABLE topics ADD COLUMN mastery_status VARCHAR(20) NOT NULL DEFAULT 'not_started'")
    if "last_reviewed_at" not in topic_columns:
        statements.append(f"ALTER TABLE topics ADD COLUMN last_reviewed_at {timestamp_type}")

    if "study_plan_items" in inspector.get_table_names():
        item_columns = {column["name"] for column in inspector.get_columns("study_plan_items")}
        if "status" not in item_columns:
            statements.append("ALTER TABLE study_plan_items ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'")
        if "started_at" not in item_columns:
            statements.append(f"ALTER TABLE study_plan_items ADD COLUMN started_at {timestamp_type}")
        if "completed_at" not in item_columns:
            statements.append(f"ALTER TABLE study_plan_items ADD COLUMN completed_at {timestamp_type}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
