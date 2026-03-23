from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import settings

# Создание асинхронного движка
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Создание фабрики сессий
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для FastAPI"""
    async with async_session_maker() as session:
        yield session


async def create_tables():
    """Создает все таблицы в БД"""
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Удаляет все таблицы"""
    from database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)