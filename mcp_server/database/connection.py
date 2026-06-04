"""
Database connection pool management with asyncio support.

This module provides async database connection pooling using SQLAlchemy 2.0
with asyncpg driver for PostgreSQL. It handles connection lifecycle, pooling,
and provides utilities for database operations.
"""

import logging
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from config import settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages async database connections and session lifecycle."""

    _engine: Optional[AsyncEngine] = None
    _session_factory = None

    @classmethod
    async def initialize(cls) -> None:
        """Initialize database connection pool."""
        if cls._engine is not None:
            logger.warning("Database already initialized")
            return

        try:
            # Create async engine with connection pooling
            cls._engine = create_async_engine(
                settings.database_url,
                echo=settings.debug,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_timeout=settings.database_pool_timeout,
                pool_recycle=settings.database_pool_recycle,
                pool_pre_ping=True,  # Test connections before using
                connect_args={
                    "timeout": 10,
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "hospital_clinical_mcp",
                        "jit": "off",
                    },
                },
            )

            # Create session factory
            from sqlalchemy.orm import sessionmaker

            cls._session_factory = sessionmaker(
                cls._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            logger.info("Database connection pool initialized successfully")

            # Test connection
            async with cls._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")

        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise

    @classmethod
    async def close(cls) -> None:
        """Close database connection pool."""
        if cls._engine is None:
            logger.warning("Database not initialized")
            return

        try:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise

    @classmethod
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session for use in async context."""
        if cls._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        async with cls._session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

    @classmethod
    async def get_engine(cls) -> AsyncEngine:
        """Get async engine for direct operations."""
        if cls._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return cls._engine

    @classmethod
    async def health_check(cls) -> bool:
        """Check database connection health."""
        try:
            engine = await cls.get_engine()
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @classmethod
    async def get_pool_status(cls) -> dict:
        """Get connection pool status."""
        if cls._engine is None:
            return {"status": "not_initialized"}

        pool = cls._engine.pool
        return {
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }


# Convenience function for dependency injection in FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session."""
    async for session in DatabaseConnection.get_session():
        yield session
