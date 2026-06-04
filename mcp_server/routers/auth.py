"""
FastAPI router for authentication endpoints.

Provides JWT token issuance for development/test credentials.
In production, integrate with the hospital identity provider (LDAP/OAuth2).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from mcp_server.models.schemas import ClinicianIdentity, ErrorResponse, TokenRequest, TokenResponse
from mcp_server.security.auth import AuthenticationManager
from mcp_server.security.audit_logger import audit_logger
from mcp_server.security.credentials import CredentialValidator
from mcp_server.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

_auth_manager = AuthenticationManager()


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
)
async def obtain_token(request: TokenRequest) -> TokenResponse:
    """
    Obtain a JWT bearer token.

    Validates credentials against the configured identity store and returns
    a signed JWT token valid for the configured expiration period.
    """
    clinician = CredentialValidator.validate_credentials(
        request.username, request.password
    )

    audit_logger.log_authentication_attempt(
        username=request.username,
        success=clinician is not None,
        failure_reason=None if clinician else "invalid credentials",
    )

    if clinician is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Override role/care_units from request if provided (and permitted in dev)
    role = request.role or clinician["role"]
    care_units = request.care_units if request.care_units is not None else clinician["care_units"]

    token = _auth_manager.create_access_token(
        clinician_id=clinician["id"],
        clinician_name=clinician["name"],
        role=role,
        care_units=care_units,
    )

    expiry_seconds = _auth_manager.expiration_hours * 3600
    logger.info(f"Token issued for clinician {clinician['id']} role={role}")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expiry_seconds,
        clinician=ClinicianIdentity(
            id=clinician["id"],
            name=clinician["name"],
            role=role,
            care_units=care_units,
        ),
    )
