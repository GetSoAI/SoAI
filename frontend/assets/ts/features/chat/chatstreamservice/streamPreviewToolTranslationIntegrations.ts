/* SoAI - Chat stream integration tool status preview translation [frontend/assets/ts/features/chat/chatstreamservice/streamPreviewToolTranslationIntegrations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';

const translateChatStreamIntegrationToolPreviewKey = (previewKey: string, previewArguments: JsonRecord | undefined): string | null => {
    switch (previewKey) {
        case 'chat.stream.preview.tools.calendar_account_sync.1':
            return i18n.t('chat.stream.preview.tools.calendar_account_sync.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_accounts_list.1':
            return i18n.t('chat.stream.preview.tools.calendar_accounts_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_calendars_list.1':
            return i18n.t('chat.stream.preview.tools.calendar_calendars_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_event_read.1':
            return i18n.t('chat.stream.preview.tools.calendar_event_read.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_event_update.1':
            return i18n.t('chat.stream.preview.tools.calendar_event_update.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_events_list.1':
            return i18n.t('chat.stream.preview.tools.calendar_events_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_invite_respond.1':
            return i18n.t('chat.stream.preview.tools.calendar_invite_respond.1', previewArguments).trim();
        case 'chat.stream.preview.tools.calendar_window_sync.1':
            return i18n.t('chat.stream.preview.tools.calendar_window_sync.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_config_get.1':
            return i18n.t('chat.stream.preview.tools.knowledge_config_get.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_ingest.1':
            return i18n.t('chat.stream.preview.tools.knowledge_ingest.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_ingest.detail.1':
            return i18n.t('chat.stream.preview.tools.knowledge_ingest.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_list.1':
            return i18n.t('chat.stream.preview.tools.knowledge_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_reindex.1':
            return i18n.t('chat.stream.preview.tools.knowledge_reindex.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_reindex.2':
            return i18n.t('chat.stream.preview.tools.knowledge_reindex.2', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_reindex.detail.1':
            return i18n.t('chat.stream.preview.tools.knowledge_reindex.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_reindex.detail.2':
            return i18n.t('chat.stream.preview.tools.knowledge_reindex.detail.2', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_search.1':
            return i18n.t('chat.stream.preview.tools.knowledge_search.1', previewArguments).trim();
        case 'chat.stream.preview.tools.knowledge_search.detail.1':
            return i18n.t('chat.stream.preview.tools.knowledge_search.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_account_sync.1':
            return i18n.t('chat.stream.preview.tools.mail_account_sync.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_accounts_list.1':
            return i18n.t('chat.stream.preview.tools.mail_accounts_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_attachment_download.1':
            return i18n.t('chat.stream.preview.tools.mail_attachment_download.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_folder_backfill.1':
            return i18n.t('chat.stream.preview.tools.mail_folder_backfill.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_folder_update.1':
            return i18n.t('chat.stream.preview.tools.mail_folder_update.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_folders_list.1':
            return i18n.t('chat.stream.preview.tools.mail_folders_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_message_compose.1':
            return i18n.t('chat.stream.preview.tools.mail_message_compose.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_message_read.1':
            return i18n.t('chat.stream.preview.tools.mail_message_read.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_message_update.1':
            return i18n.t('chat.stream.preview.tools.mail_message_update.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_messages_list.1':
            return i18n.t('chat.stream.preview.tools.mail_messages_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mail_messages_remote_search.1':
            return i18n.t('chat.stream.preview.tools.mail_messages_remote_search.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mcp_resource_read.1':
            return i18n.t('chat.stream.preview.tools.mcp_resource_read.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mcp_resource_read.detail.1':
            return i18n.t('chat.stream.preview.tools.mcp_resource_read.detail.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mcp_resource_templates_list.1':
            return i18n.t('chat.stream.preview.tools.mcp_resource_templates_list.1', previewArguments).trim();
        case 'chat.stream.preview.tools.mcp_resources_list.1':
            return i18n.t('chat.stream.preview.tools.mcp_resources_list.1', previewArguments).trim();
        default:
            return null;
    }
};

export { translateChatStreamIntegrationToolPreviewKey };
