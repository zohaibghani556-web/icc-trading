from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

url = settings.DATABASE_URL
for old, new in [
    ("postgresql+asyncpg://", "postgresql://"),
    ("postgresql+psycopg://", "postgresql://"),
    ("postgresql+psycopg2://", "postgresql://"),
    ("sqlite+aiosqlite://", "sqlite://"),
]:
    url = url.replace(old, new)

is_sqlite = url.startswith("sqlite")

if is_sqlite:
    engine = create_engine(url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
        connect_args={"sslmode": "require", "connect_timeout": 10},
    )

SyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def create_tables():
    from app.models import alert, signal, setup, trade, user, instrument, icc_config
    Base.metadata.create_all(bind=engine)

async def get_db():
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
