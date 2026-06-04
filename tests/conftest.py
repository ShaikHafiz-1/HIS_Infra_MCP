"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from main import app
from mcp_server.database.models import Base
from config import settings


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clear the in-memory cache before each test to prevent cross-test contamination."""
    from mcp_server.database.cache import cache
    cache.flush_all()
    yield
    cache.flush_all()


@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_patient_id():
    """Provide a sample patient ID for testing."""
    return "PAT-12345678-1234-1234-1234-123456789012"


@pytest.fixture
def sample_encounter_id():
    """Provide a sample encounter ID for testing."""
    return "ENC-12345678-1234-1234-1234-123456789012"


@pytest.fixture
def sample_device_id():
    """Provide a sample device ID for testing."""
    return "DEV-12345678-1234-1234-1234-123456789012"


@pytest.fixture
async def db_session():
    """Provide an async database session for testing."""
    # Create test database engine using SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Create session
    async with async_session() as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
