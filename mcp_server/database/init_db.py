"""
Database initialization script for Hospital Clinical Intelligence MCP Platform.

This script initializes the database schema and can be run during deployment
or development setup.
"""

import asyncio
import logging
import sys
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine

from config import settings
from mcp_server.database.connection import DatabaseConnection
from mcp_server.database.models import Base

logger = logging.getLogger(__name__)


async def create_tables() -> bool:
    """Create all database tables from ORM models.
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        logger.info("Creating database tables...")
        
        # Create async engine
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
        )
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await engine.dispose()
        logger.info("Database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


async def drop_tables() -> bool:
    """Drop all database tables.
    
    WARNING: This will delete all data!
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        logger.warning("Dropping all database tables...")
        
        # Create async engine
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
        )
        
        # Drop all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        await engine.dispose()
        logger.warning("Database tables dropped successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        return False


async def init_database() -> bool:
    """Initialize database connection and create tables.
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        logger.info("Initializing database...")
        
        # Initialize connection pool
        await DatabaseConnection.initialize()
        
        # Create tables
        success = await create_tables()
        
        # Close connection
        await DatabaseConnection.close()
        
        if success:
            logger.info("Database initialization completed successfully")
        else:
            logger.error("Database initialization failed")
        
        return success
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


async def health_check() -> bool:
    """Check database connection health.
    
    Returns:
        True if database is healthy, False otherwise.
    """
    try:
        logger.info("Checking database health...")
        
        # Initialize connection pool
        await DatabaseConnection.initialize()
        
        # Check health
        is_healthy = await DatabaseConnection.health_check()
        
        # Get pool status
        pool_status = await DatabaseConnection.get_pool_status()
        logger.info(f"Connection pool status: {pool_status}")
        
        # Close connection
        await DatabaseConnection.close()
        
        if is_healthy:
            logger.info("Database health check passed")
        else:
            logger.error("Database health check failed")
        
        return is_healthy
        
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return False


async def main(command: Optional[str] = None) -> int:
    """Main entry point for database initialization.
    
    Args:
        command: Command to execute ('init', 'drop', 'health')
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Configure logging
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    if command == "init":
        success = await init_database()
        return 0 if success else 1
    elif command == "drop":
        success = await drop_tables()
        return 0 if success else 1
    elif command == "health":
        success = await health_check()
        return 0 if success else 1
    else:
        logger.error(f"Unknown command: {command}")
        logger.info("Available commands: init, drop, health")
        return 1


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "init"
    exit_code = asyncio.run(main(command))
    sys.exit(exit_code)
