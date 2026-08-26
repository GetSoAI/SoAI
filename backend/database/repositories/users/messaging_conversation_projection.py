"""SoAI - Live Messaging account authority projection SQL [backend/database/repositories/users/messaging_conversation_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "MESSAGING_CONVERSATION_AUTHORITY_JOIN_SQL",
    "MESSAGING_CONVERSATION_AUTHORITY_SELECT_SQL",
)

MESSAGING_CONVERSATION_AUTHORITY_SELECT_SQL = """
messaging_account.account_id AS messaging_account_id,
messaging_account.label AS messaging_live_account_label,
messaging_account.model_settings_json AS messaging_account_model_settings
"""

MESSAGING_CONVERSATION_AUTHORITY_JOIN_SQL = """
LEFT JOIN messaging_thread_bindings AS messaging_binding
  ON messaging_binding.conv_id = c.id
 AND messaging_binding.user_id = c.user_id
LEFT JOIN messaging_accounts AS messaging_account
  ON messaging_account.account_id = messaging_binding.account_id
 AND messaging_account.user_id = c.user_id
"""
