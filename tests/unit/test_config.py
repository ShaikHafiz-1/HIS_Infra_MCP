"""Tests for configuration management."""

import pytest

from config import settings


class TestSettings:
    """Test configuration settings."""

    def test_settings_loaded(self):
        """Test that settings are loaded correctly."""
        assert settings is not None
        assert settings.environment is not None
        assert settings.server_host is not None
        assert settings.server_port > 0

    def test_is_development(self):
        """Test development environment check."""
        # Settings default to development
        assert settings.is_development() or settings.is_production()

    def test_database_url(self):
        """Test database URL is configured."""
        assert settings.database_url is not None
        assert "postgresql" in settings.database_url or "asyncpg" in settings.database_url

    def test_redis_url(self):
        """Test Redis URL is configured."""
        assert settings.redis_url is not None
        assert "redis" in settings.redis_url

    def test_rabbitmq_url(self):
        """Test RabbitMQ URL is configured."""
        assert settings.rabbitmq_url is not None
        assert "amqp" in settings.rabbitmq_url

    def test_jwt_configuration(self):
        """Test JWT configuration."""
        assert settings.jwt_secret_key is not None
        assert settings.jwt_algorithm is not None
        assert settings.jwt_expiration_hours > 0

    def test_hl7_listener_configuration(self):
        """Test HL7 listener configuration."""
        assert settings.hl7_listener_host is not None
        assert settings.hl7_listener_port > 0

    def test_dicom_listener_configuration(self):
        """Test DICOM listener configuration."""
        assert settings.dicom_listener_host is not None
        assert settings.dicom_listener_port > 0

    def test_fhir_configuration(self):
        """Test FHIR configuration."""
        assert settings.fhir_server_url is not None
        assert settings.fhir_client_id is not None

    def test_feature_flags(self):
        """Test feature flags are configured."""
        assert isinstance(settings.enable_hl7_ingestion, bool)
        assert isinstance(settings.enable_fhir_ingestion, bool)
        assert isinstance(settings.enable_dicom_ingestion, bool)
        assert isinstance(settings.enable_device_telemetry, bool)
