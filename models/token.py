from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class RefreshToken(Base):
    """
    Refresh token record for JWT session management.

    Design notes:
    - Refresh tokens are stored only as hashes for security.
    - Rotation is supported via replaced_by_token_hash.
    - Revocation is supported via revoked_at.

    Fields:
        user_id: Owner of this refresh token.
        token_hash: Hash of the refresh token (unique and indexed).
        created_at: When this token record was created.
        expires_at: When this token becomes invalid.
        revoked_at: If set, the token is revoked and must not be accepted.
        replaced_by_token_hash: Hash of the next token created during rotation.

    Relationships:
        user: User who owns this refresh token.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    revoked_at = Column(DateTime, nullable=True, index=True)
    replaced_by_token_hash = Column(String(64), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")