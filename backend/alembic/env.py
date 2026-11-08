import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.db.models import Base

target_metadata = Base.metadata


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _online():
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_online())
