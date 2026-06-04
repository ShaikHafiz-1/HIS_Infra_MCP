"""
Configuration management for Hospital Clinical Intelligence MCP Platform.

This module handles all configuration settings using environment variables
with sensible defaults for development. Configuration is loaded from .env files
and environment variables.
"""

import os
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI Configuration
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Server Configuration
    server_host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("SERVER_PORT", "8000"))
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")

    # Database Configuration
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/hospital_clinical_mcp"
    )
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "20"))
    database_max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
    database_pool_timeout: int = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
    database_pool_recycle: int = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))

    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_cache_ttl: int = int(os.getenv("REDIS_CACHE_TTL", "3600"))

    # RabbitMQ Configuration
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    rabbitmq_queue_hl7: str = os.getenv("RABBITMQ_QUEUE_HL7", "hl7_messages")
    rabbitmq_queue_fhir: str = os.getenv("RABBITMQ_QUEUE_FHIR", "fhir_resources")
    rabbitmq_queue_dicom: str = os.getenv("RABBITMQ_QUEUE_DICOM", "dicom_metadata")
    rabbitmq_queue_device: str = os.getenv("RABBITMQ_QUEUE_DEVICE", "device_telemetry")

    # HL7 Listener Configuration
    hl7_listener_host: str = os.getenv("HL7_LISTENER_HOST", "0.0.0.0")
    hl7_listener_port: int = int(os.getenv("HL7_LISTENER_PORT", "2575"))
    hl7_listener_timeout: int = int(os.getenv("HL7_LISTENER_TIMEOUT", "300"))

    # FHIR Configuration
    fhir_server_url: str = os.getenv("FHIR_SERVER_URL", "https://fhir.hospital.local/fhir")
    fhir_client_id: str = os.getenv("FHIR_CLIENT_ID", "mcp_server")
    fhir_client_secret: str = os.getenv("FHIR_CLIENT_SECRET", "")
    fhir_oauth_token_url: str = os.getenv(
        "FHIR_OAUTH_TOKEN_URL",
        "https://auth.hospital.local/oauth/token"
    )
    fhir_sync_interval: int = int(os.getenv("FHIR_SYNC_INTERVAL", "3600"))

    # DICOM Configuration
    dicom_listener_host: str = os.getenv("DICOM_LISTENER_HOST", "0.0.0.0")
    dicom_listener_port: int = int(os.getenv("DICOM_LISTENER_PORT", "11112"))
    dicom_ae_title: str = os.getenv("DICOM_AE_TITLE", "MCP_SERVER")
    dicom_archive_url: str = os.getenv("DICOM_ARCHIVE_URL", "http://dicom-archive.hospital.local")

    # Device Telemetry Configuration
    device_telemetry_port: int = int(os.getenv("DEVICE_TELEMETRY_PORT", "9000"))
    device_telemetry_timeout: int = int(os.getenv("DEVICE_TELEMETRY_TIMEOUT", "60"))

    # Authentication Configuration
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    oauth2_provider_url: str = os.getenv("OAUTH2_PROVIDER_URL", "https://auth.hospital.local")
    ldap_server_url: str = os.getenv("LDAP_SERVER_URL", "ldap://ldap.hospital.local")
    ldap_base_dn: str = os.getenv("LDAP_BASE_DN", "dc=hospital,dc=local")

    # Authorization Configuration
    rbac_enabled: bool = os.getenv("RBAC_ENABLED", "true").lower() == "true"
    consent_checking_enabled: bool = os.getenv("CONSENT_CHECKING_ENABLED", "true").lower() == "true"

    # Security Configuration
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080"
    ]
    cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_allow_headers: List[str] = ["*"]

    # Audit Logging Configuration
    audit_log_enabled: bool = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
    audit_log_retention_days: int = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "2555"))
    phi_masking_enabled: bool = os.getenv("PHI_MASKING_ENABLED", "true").lower() == "true"

    # Performance Configuration
    query_timeout_seconds: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))

    # Monitoring Configuration
    metrics_enabled: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    metrics_port: int = int(os.getenv("METRICS_PORT", "9090"))
    health_check_interval: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))

    # Logging Configuration
    log_format: str = os.getenv("LOG_FORMAT", "json")
    log_file_path: str = os.getenv("LOG_FILE_PATH", "./logs/app.log")
    log_file_max_bytes: int = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))
    log_file_backup_count: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "10"))

    # Feature Flags
    enable_hl7_ingestion: bool = os.getenv("ENABLE_HL7_INGESTION", "true").lower() == "true"
    enable_fhir_ingestion: bool = os.getenv("ENABLE_FHIR_INGESTION", "true").lower() == "true"
    enable_dicom_ingestion: bool = os.getenv("ENABLE_DICOM_INGESTION", "true").lower() == "true"
    enable_device_telemetry: bool = os.getenv("ENABLE_DEVICE_TELEMETRY", "true").lower() == "true"
    enable_caching: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    enable_audit_logging: bool = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def get_database_url(self) -> str:
        """Get database URL with proper formatting."""
        return self.database_url

    def get_redis_url(self) -> str:
        """Get Redis URL with proper formatting."""
        return self.redis_url

    def get_rabbitmq_url(self) -> str:
        """Get RabbitMQ URL with proper formatting."""
        return self.rabbitmq_url


# Global settings instance
settings = Settings()
