"""
Authentication module for Hospital Clinical Intelligence MCP Platform.

This module provides JWT token generation and validation for clinician authentication.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from config import settings
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)
security = HTTPBearer()


class AuthenticationError(Exception):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


class TokenExpiredError(AuthenticationError):
    """JWT token has expired."""

    def __init__(self):
        super().__init__("Token has expired")


class InvalidTokenError(AuthenticationError):
    """JWT token is invalid."""

    def __init__(self):
        super().__init__("Invalid token")


class AuthenticationManager:
    """Manages JWT token generation and validation for clinicians."""

    def __init__(
        self,
        secret_key: str = settings.jwt_secret_key,
        algorithm: str = settings.jwt_algorithm,
        expiration_hours: int = settings.jwt_expiration_hours,
    ):
        """
        Initialize authentication manager.

        Args:
            secret_key: Secret key for JWT encoding/decoding
            algorithm: JWT algorithm (default: HS256)
            expiration_hours: Token expiration time in hours
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiration_hours = expiration_hours

    def create_access_token(
        self,
        clinician_id: str,
        clinician_name: str,
        role: str,
        care_units: Optional[list] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create JWT access token for a clinician.

        Args:
            clinician_id: Unique identifier for the clinician
            clinician_name: Name of the clinician
            role: Role of the clinician (physician, nurse, technician, administrator)
            care_units: List of care unit IDs the clinician is assigned to
            expires_delta: Custom expiration time (default: from settings)

        Returns:
            str: Encoded JWT token

        Raises:
            AuthenticationError: If token creation fails
        """
        if care_units is None:
            care_units = []

        if expires_delta is None:
            expires_delta = timedelta(hours=self.expiration_hours)

        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        to_encode = {
            "sub": clinician_id,
            "name": clinician_name,
            "role": role,
            "care_units": care_units,
            "exp": expire,
            "iat": now,
        }

        try:
            encoded_jwt = jwt.encode(
                to_encode, self.secret_key, algorithm=self.algorithm
            )
            logger.debug(f"Created access token for clinician: {clinician_id}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise AuthenticationError("Failed to create access token")

    def verify_token(self, token: str) -> Dict:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token to verify

        Returns:
            dict: Decoded token payload

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            clinician_id = payload.get("sub")

            if clinician_id is None:
                logger.warning("Token missing 'sub' claim")
                raise InvalidTokenError()

            logger.debug(f"Verified token for clinician: {clinician_id}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise TokenExpiredError()
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise InvalidTokenError()
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise InvalidTokenError()

    def validate_clinician_identity(self, payload: Dict) -> Dict:
        """
        Validate clinician identity from token payload.

        Args:
            payload: Decoded JWT payload

        Returns:
            dict: Clinician identity information

        Raises:
            InvalidTokenError: If clinician identity is invalid
        """
        required_fields = ["sub", "name", "role"]

        for field in required_fields:
            if field not in payload:
                logger.warning(f"Token missing required field: {field}")
                raise InvalidTokenError()

        clinician_identity = {
            "id": payload["sub"],
            "name": payload["name"],
            "role": payload["role"],
            "care_units": payload.get("care_units", []),
        }

        logger.debug(f"Validated clinician identity: {clinician_identity['id']}")
        return clinician_identity


# Global authentication manager instance
auth_manager = AuthenticationManager()


async def get_current_clinician(
    credentials: HTTPBearer = Depends(security),
) -> Dict:
    """
    Dependency to get current authenticated clinician from request.

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        dict: Clinician identity information

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    try:
        payload = auth_manager.verify_token(token)
        clinician = auth_manager.validate_clinician_identity(payload)
        return clinician
    except TokenExpiredError:
        logger.warning("Token expired in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        logger.warning("Invalid token in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
