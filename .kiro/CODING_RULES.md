# Hospital Clinical Intelligence MCP Platform - Coding Rules

This document establishes coding standards and best practices for the Hospital Clinical Intelligence MCP Platform to ensure consistency, maintainability, and production-grade quality.

## Python Version & Compatibility

### Python 3.14+ Compatibility
- **REQUIRED**: Use timezone-aware datetime objects
- **DEPRECATED**: `datetime.utcnow()` is deprecated in Python 3.12+ and will be removed in Python 3.14+
- **CORRECT**: Use `datetime.now(timezone.utc)` instead

#### Migration Guide
```python
# ❌ WRONG - Deprecated
from datetime import datetime
timestamp = datetime.utcnow()

# ✅ CORRECT - Python 3.14+ compatible
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

#### SQLAlchemy Default Values
```python
# ❌ WRONG - Deprecated
created_at: Mapped[datetime] = mapped_column(
    DateTime, default=datetime.utcnow, nullable=False
)

# ✅ CORRECT - Python 3.14+ compatible
created_at: Mapped[datetime] = mapped_column(
    DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
)
```

## Dependency Management

### Version Pinning
- **REQUIRED**: Always use exact/pinned versions in `requirements.txt`
- **REASON**: Ensures reproducible builds and prevents unexpected breaking changes
- **FORMAT**: `package==X.Y.Z` (not `package>=X.Y.Z` or `package~=X.Y.Z`)

### Dependency Compatibility
- **SQLAlchemy**: Use version 2.0.49+ for Python 3.14 compatibility
- **Pydantic**: Use version 2.13.4+ for Python 3.14 compatibility
- **FastAPI**: Use version 0.115.0+ for compatibility with latest dependencies
- **aiosqlite**: Required for async SQLite testing (version 0.20.0+)
- **Faker**: Required for test data generation (version 20.1.0+)

### Known Compatibility Issues
- SQLAlchemy < 2.0.49: Has typing issues with Python 3.14
- Pydantic < 2.13.4: May have compatibility issues with newer Python versions
- FastAPI < 0.115.0: May have dependency conflicts with newer versions of anyio

## Code Style & Formatting

### Imports
- Use `from datetime import datetime, timezone` for timezone-aware operations
- Group imports: standard library, third-party, local
- Use absolute imports, not relative imports

### Type Hints
- **REQUIRED**: All function parameters and return types must have type hints
- **REQUIRED**: Use `Optional[T]` for nullable types, not `T | None`
- **REQUIRED**: Use `Mapped[T]` for SQLAlchemy ORM fields

### Docstrings
- **REQUIRED**: All modules, classes, and public functions must have docstrings
- **FORMAT**: Use triple-quoted strings with description, args, returns, raises
- **EXAMPLE**:
```python
def get_patient_context(patient_id: str) -> Dict[str, Any]:
    """
    Retrieve clinical context for a patient.
    
    Args:
        patient_id: Internal patient identifier
        
    Returns:
        Dictionary containing patient demographics, encounters, and clinical data
        
    Raises:
        ValueError: If patient_id is invalid
        DatabaseError: If database query fails
    """
```

## Database & ORM

### SQLAlchemy Models
- **REQUIRED**: All models must inherit from `Base` (DeclarativeBase)
- **REQUIRED**: All models must have `__tablename__` defined
- **REQUIRED**: All models must have primary key defined
- **REQUIRED**: All models must have audit fields: `created_at`, `updated_at`, `deleted_at`
- **REQUIRED**: Use `Mapped[T]` type hints for all columns
- **REQUIRED**: Use `mapped_column()` for column definitions

### Audit Fields Pattern
```python
# ✅ CORRECT - All models should follow this pattern
created_at: Mapped[datetime] = mapped_column(
    DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
)
updated_at: Mapped[datetime] = mapped_column(
    DateTime, 
    default=lambda: datetime.now(timezone.utc), 
    onupdate=lambda: datetime.now(timezone.utc), 
    nullable=False
)
deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

### Soft Deletes
- **REQUIRED**: Use soft deletes (set `is_deleted=True` and `deleted_at=timestamp`)
- **NEVER**: Physically delete records from production databases
- **REASON**: Maintains audit trail and data integrity

### Indexing
- **REQUIRED**: Add indexes for frequently queried columns
- **REQUIRED**: Add composite indexes for multi-field queries
- **PATTERN**: Use `__table_args__` tuple with `Index()` objects

### Relationships
- **REQUIRED**: Use `relationship()` for ORM relationships
- **REQUIRED**: Use `back_populates` for bidirectional relationships
- **REQUIRED**: Use `cascade="all, delete-orphan"` for dependent relationships

## Testing

### Test File Organization
- **LOCATION**: All tests in `tests/unit/` directory
- **NAMING**: Test files named `test_*.py`
- **CLASSES**: Test classes named `Test*`
- **METHODS**: Test methods named `test_*`

### Test Fixtures
- **REQUIRED**: Use pytest fixtures for setup/teardown
- **REQUIRED**: Use `@pytest.fixture` decorator
- **PATTERN**: Fixtures should be reusable and focused

### Async Testing
- **REQUIRED**: Use `@pytest.mark.asyncio` for async tests
- **REQUIRED**: Use `async def` for async test functions
- **REQUIRED**: Use `await` for async operations

### Test Data Generation
- **REQUIRED**: Use Faker library for realistic test data
- **REQUIRED**: Generate unique IDs using UUID4
- **REQUIRED**: Use timezone-aware datetimes in test data

## Logging

### Structured Logging
- **REQUIRED**: Use JSON logging format for production
- **REQUIRED**: Include timestamp, level, logger name, message
- **REQUIRED**: Include context fields: request_id, user_id, patient_id (when applicable)

### Logger Setup
```python
# ✅ CORRECT - Use timezone-aware timestamps
from datetime import datetime, timezone
import json

log_data = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "level": record.levelname,
    "message": record.getMessage(),
}
```

## Security & Compliance

### PHI Protection
- **REQUIRED**: Never log patient names, MRNs, or medical record numbers
- **REQUIRED**: Mask sensitive data in error messages
- **REQUIRED**: Use audit logging for all data access

### Authentication
- **REQUIRED**: Use JWT tokens with expiration
- **REQUIRED**: Validate tokens on every request
- **REQUIRED**: Use HTTPS for all communications

### Authorization
- **REQUIRED**: Implement role-based access control (RBAC)
- **REQUIRED**: Check permissions before data access
- **REQUIRED**: Log all authorization decisions

## Performance

### Database Queries
- **REQUIRED**: Use indexes for all frequently queried columns
- **REQUIRED**: Use composite indexes for multi-field queries
- **REQUIRED**: Avoid N+1 queries (use eager loading with relationships)
- **REQUIRED**: Monitor slow queries (> 1 second)

### Caching
- **REQUIRED**: Use Redis for frequently accessed data
- **REQUIRED**: Implement cache invalidation on data updates
- **REQUIRED**: Set appropriate TTLs for cached data

### Response Times
- **REQUIRED**: Tool responses must complete within 2 seconds
- **REQUIRED**: Monitor response times for all tools
- **REQUIRED**: Alert on performance degradation

## Healthcare Data Handling

### HL7 v2 Messages
- **REQUIRED**: Validate all HL7 messages before processing
- **REQUIRED**: Extract and normalize patient IDs
- **REQUIRED**: Handle missing or malformed fields gracefully
- **REQUIRED**: Log parsing errors for manual review

### FHIR Resources
- **REQUIRED**: Validate FHIR resources against schema
- **REQUIRED**: Map FHIR resources to internal data model
- **REQUIRED**: Maintain FHIR resource ID mappings
- **REQUIRED**: Handle resource versioning

### Device Telemetry
- **REQUIRED**: Validate vital sign ranges
- **REQUIRED**: Detect and flag missing or delayed data
- **REQUIRED**: Associate telemetry with correct patient/encounter
- **REQUIRED**: Maintain device calibration status

## Error Handling

### Exception Handling
- **REQUIRED**: Use specific exception types (not generic `Exception`)
- **REQUIRED**: Include context in exception messages
- **REQUIRED**: Log exceptions with full traceback
- **REQUIRED**: Return appropriate HTTP status codes

### Database Errors
- **REQUIRED**: Handle connection failures gracefully
- **REQUIRED**: Implement retry logic for transient failures
- **REQUIRED**: Log database errors for debugging

### Validation Errors
- **REQUIRED**: Validate all inputs before processing
- **REQUIRED**: Return 400 Bad Request for invalid inputs
- **REQUIRED**: Include validation error details in response

## Documentation

### Code Comments
- **REQUIRED**: Comment complex logic and business rules
- **REQUIRED**: Explain WHY, not WHAT (code shows what)
- **REQUIRED**: Keep comments up-to-date with code changes

### API Documentation
- **REQUIRED**: Document all MCP tools with descriptions
- **REQUIRED**: Document input and output schemas
- **REQUIRED**: Provide example queries for each tool
- **REQUIRED**: Document error responses

### Operational Documentation
- **REQUIRED**: Create deployment guides
- **REQUIRED**: Create troubleshooting guides
- **REQUIRED**: Document configuration options
- **REQUIRED**: Document monitoring and alerting

## Deployment

### Configuration Management
- **REQUIRED**: Use environment variables for configuration
- **REQUIRED**: Never commit secrets to version control
- **REQUIRED**: Use `.env.example` for configuration template
- **REQUIRED**: Document all configuration options

### Database Migrations
- **REQUIRED**: Use Alembic for schema migrations
- **REQUIRED**: Create migration for every schema change
- **REQUIRED**: Test migrations before deployment
- **REQUIRED**: Maintain migration history

### Health Checks
- **REQUIRED**: Implement `/health` endpoint for system status
- **REQUIRED**: Implement `/ready` endpoint for readiness checks
- **REQUIRED**: Check database connectivity in health checks
- **REQUIRED**: Return appropriate HTTP status codes

## Continuous Improvement

### Code Review
- **REQUIRED**: All code changes must be reviewed
- **REQUIRED**: Review for correctness, security, and performance
- **REQUIRED**: Verify compliance with coding rules
- **REQUIRED**: Approve before merging

### Testing
- **REQUIRED**: All code changes must have tests
- **REQUIRED**: Maintain > 80% code coverage
- **REQUIRED**: Run full test suite before deployment
- **REQUIRED**: Fix failing tests before merging

### Monitoring
- **REQUIRED**: Monitor application performance
- **REQUIRED**: Monitor error rates and exceptions
- **REQUIRED**: Monitor database performance
- **REQUIRED**: Alert on anomalies

## Summary

These coding rules ensure:
- ✅ Python 3.14+ compatibility
- ✅ Production-grade code quality
- ✅ Healthcare data security and compliance
- ✅ Maintainability and scalability
- ✅ Consistent team standards

**All code must comply with these rules before deployment.**
