from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

url = settings.DATABASE_URL
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
if url.startswith("postgresql+asyncpg://"):
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
if url.startswith("postgresql+psycopg://"):
    url = url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)

is_sqlite = url.startswith("sqlite")
if is_sqlite:
    url = url.replace("sqlite://", "sqlite+aiosqlite://")
    engine = create_async_engine(url, echo=False, connect_args={"check_same_thread": False})
else:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    sync_engine = create_engine(url, echo=False)
    engine = sync_engine

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

if is_sqlite:
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
else:
    from sqlalchemy.orm import sessionmaker
    SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)

async def create_tables():
    from app.models import alert, signal, setup, trade, user, instrument, icc_config
    if is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        Base.metadata.create_all(bind=sync_engine)

async def get_db():
    if is_sqlite:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    else:
        session = SyncSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
