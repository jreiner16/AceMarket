"""Firebase API authentication"""
import os
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import DISABLE_AUTH

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        try:
            import firebase_admin
            from firebase_admin import credentials
            if not firebase_admin._apps:
                cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    _firebase_app = firebase_admin.initialize_app(cred)
                else:
                    # Use default credentials (e.g. GCP env)
                    _firebase_app = firebase_admin.initialize_app()
        except Exception as e:
            logger.error("Firebase init failed: %s", e)
            raise
    return _firebase_app


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """Verify Firebase ID token and return user ID. Raises 401 if invalid."""
    if DISABLE_AUTH:
        return "dev-user"
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        try:
            from firebase_admin import auth
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Firebase Admin SDK not installed. Run: pip install firebase-admin",
            ) from None
        _get_firebase_app()
        decoded = auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return uid
    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
