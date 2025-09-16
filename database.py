"""
Database connection and session management utilities.

This module provides database connection setup and session management
"""
import os
import logging
from contextlib import asynccontextmanager
from sqlmodel import create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

db_logger = logging.getLogger('bot.database')

engine = None
async_engine = None
async_session_factory = None


def init_database():
    """
    Initialize database connection and create engine.

    This function should be called once during bot startup.
    """
    global engine, async_engine, async_session_factory

    database_url = os.getenv('DATABASE_URL')
    db_logger.debug(f"Database URL: {database_url}")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please add DATABASE_URL=your_database_connection_string to your .env file"
        )

    engine = create_engine(database_url, echo=False)

    async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')

    async_engine = create_async_engine(async_database_url, echo=False)
    async_session_factory = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    db_logger.info("Database connection initialized successfully")


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_async_session() as session:
            # Use session here
            pass

    Yields:
        AsyncSession: Database session for async operations
    """
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            db_logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


def get_sync_session() -> Session:
    """
    Get a synchronous database session.

    Returns:
        Session: Synchronous database session

    Note:
        Remember to close the session when done:
        session = get_sync_session()
        try:
            # Use session
            pass
        finally:
            session.close()
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    return Session(engine)
