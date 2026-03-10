import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL: str = os.environ["DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that provides a transactional async DB session."""
    async with AsyncSessionFactory() as session:
        try:
            #yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
