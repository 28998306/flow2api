from sqlalchemy import text

from app.core.db import Base
from app.core.db_sync import sync_engine
from app.models import *  # noqa: F401,F403


def ensure_runtime_schema() -> None:
    """Development-friendly schema guard.

    The project currently uses metadata-based table creation. Existing local
    deployments need additive columns for new account/log/api-key features, so
    keep this limited to safe CREATE/ADD COLUMN operations.
    """

    Base.metadata.create_all(bind=sync_engine)
    statements = [
        "ALTER TABLE flow_accounts ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) NOT NULL DEFAULT 'normal'",
        "ALTER TABLE flow_accounts ADD COLUMN IF NOT EXISTS bearer_expires_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE flow_accounts ADD COLUMN IF NOT EXISTS cookies_expires_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE flow_accounts ADD COLUMN IF NOT EXISTS next_refresh_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE flow_accounts ADD COLUMN IF NOT EXISTS auto_refresh_minutes INTEGER NOT NULL DEFAULT 50",
    ]
    with sync_engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
