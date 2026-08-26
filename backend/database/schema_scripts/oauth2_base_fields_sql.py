"""SoAI - Shared OAuth2 schema field SQL fragments [backend/database/schema_scripts/oauth2_base_fields_sql.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("OAUTH2_BASE_FIELDS_SQL",)

OAUTH2_BASE_FIELDS_SQL = """
            oauth_client_id TEXT,
            oauth_client_secret_encrypted TEXT,
            oauth_access_token_encrypted TEXT,
            oauth_refresh_token_encrypted TEXT,
            oauth_expires_at_ms INTEGER,
            oauth_resource_metadata_url TEXT,
            oauth_auth_server_issuer TEXT,
            oauth_authorization_endpoint TEXT,
            oauth_token_endpoint TEXT,
            oauth_registration_endpoint TEXT,
            oauth_token_endpoint_auth_method TEXT,
"""
