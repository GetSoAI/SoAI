/* SoAI - Settings page acl action text [frontend/assets/ts/pages/settings/controllers/aclActionText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

const resolveAclActionLabel = (action: string): string => {
    switch (action) {
        case 'WIZARD_BOOTSTRAP':
            return i18n.t('settings.acl.actions.WIZARD_BOOTSTRAP');
        case 'AUTH_COOKIE':
            return i18n.t('settings.acl.actions.AUTH_COOKIE');
        case 'USER_ADMIN':
            return i18n.t('settings.acl.actions.USER_ADMIN');
        case 'CONFIG_PATCH':
            return i18n.t('settings.acl.actions.CONFIG_PATCH');
        case 'TERMINAL_USE':
            return i18n.t('settings.acl.actions.TERMINAL_USE');
        case 'HW_GPU_TUNING':
            return i18n.t('settings.acl.actions.HW_GPU_TUNING');
        case 'PLUGIN_ADMIN':
            return i18n.t('settings.acl.actions.PLUGIN_ADMIN');
        case 'FACTORY_RESET':
            return i18n.t('settings.acl.actions.FACTORY_RESET');
        case 'METRICS_RESET':
            return i18n.t('settings.acl.actions.METRICS_RESET');
        case 'REQUEST_CANCELLATION_ADMIN':
            return i18n.t('settings.acl.actions.REQUEST_CANCELLATION_ADMIN');
        case 'SYSTEM_POWER':
            return i18n.t('settings.acl.actions.SYSTEM_POWER');
        case 'MODEL_READ':
            return i18n.t('settings.acl.actions.MODEL_READ');
        case 'MODEL_ADMIN':
            return i18n.t('settings.acl.actions.MODEL_ADMIN');
        case 'MODEL_ROUTING_READ':
            return i18n.t('settings.acl.actions.MODEL_ROUTING_READ');
        case 'MODEL_ROUTING_ADMIN':
            return i18n.t('settings.acl.actions.MODEL_ROUTING_ADMIN');
        case 'NOTIFICATIONS':
            return i18n.t('settings.acl.actions.NOTIFICATIONS');
        case 'SOFTWARE_UPDATE':
            return i18n.t('settings.acl.actions.SOFTWARE_UPDATE');
        case 'LOG_ACCESS':
            return i18n.t('settings.acl.actions.LOG_ACCESS');
        case 'ACL_ADMIN':
            return i18n.t('settings.acl.actions.ACL_ADMIN');
        case 'SYSTEM_STATUS_READ':
            return i18n.t('settings.acl.actions.SYSTEM_STATUS_READ');
        case 'PLUGIN_READ':
            return i18n.t('settings.acl.actions.PLUGIN_READ');
        case 'HARDWARE_READ':
            return i18n.t('settings.acl.actions.HARDWARE_READ');
        case 'SEARCH_READ':
            return i18n.t('settings.acl.actions.SEARCH_READ');
        case 'OPENAI_API':
            return i18n.t('settings.acl.actions.OPENAI_API');
        case 'WEBUI_APPEARANCE_ADMIN':
            return i18n.t('settings.acl.actions.WEBUI_APPEARANCE_ADMIN');
        case 'OPENAI_API_ADMIN':
            return i18n.t('settings.acl.actions.OPENAI_API_ADMIN');
        case 'FILE_EXPLORER_READ':
            return i18n.t('settings.acl.actions.FILE_EXPLORER_READ');
        case 'FILE_EXPLORER_WRITE':
            return i18n.t('settings.acl.actions.FILE_EXPLORER_WRITE');
        case 'FILE_EXPLORER_HASH':
            return i18n.t('settings.acl.actions.FILE_EXPLORER_HASH');
        case 'FILE_EXPLORER_ADMIN':
            return i18n.t('settings.acl.actions.FILE_EXPLORER_ADMIN');
        case 'HOST_MANAGEMENT_ADMIN':
            return i18n.t('settings.acl.actions.HOST_MANAGEMENT_ADMIN');
        case 'MCP_ADMIN':
            return i18n.t('settings.acl.actions.MCP_ADMIN');
        case 'TASK_MANAGEMENT':
            return i18n.t('settings.acl.actions.TASK_MANAGEMENT');
        case 'HW_PROCESS_VIEW':
            return i18n.t('settings.acl.actions.HW_PROCESS_VIEW');
        case 'BACKUP_ADMIN':
            return i18n.t('settings.acl.actions.BACKUP_ADMIN');
        case 'WEB_SEARCH':
            return i18n.t('settings.acl.actions.WEB_SEARCH');
        case 'RAG_USE':
            return i18n.t('settings.acl.actions.RAG_USE');
        case 'MCP_USE':
            return i18n.t('settings.acl.actions.MCP_USE');
        case 'LICENSING_ADMIN':
            return i18n.t('settings.acl.actions.LICENSING_ADMIN');
        case 'RECOVERY_ADMIN':
            return i18n.t('settings.acl.actions.RECOVERY_ADMIN');
        default:
            throw new Error(`ACL action label mapping missing for "${action}"`);
    }
};

const resolveAclActionDescription = (action: string): string => {
    switch (action) {
        case 'WIZARD_BOOTSTRAP':
            return i18n.t('settings.acl.actionDescriptions.WIZARD_BOOTSTRAP');
        case 'AUTH_COOKIE':
            return i18n.t('settings.acl.actionDescriptions.AUTH_COOKIE');
        case 'USER_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.USER_ADMIN');
        case 'CONFIG_PATCH':
            return i18n.t('settings.acl.actionDescriptions.CONFIG_PATCH');
        case 'TERMINAL_USE':
            return i18n.t('settings.acl.actionDescriptions.TERMINAL_USE');
        case 'HW_GPU_TUNING':
            return i18n.t('settings.acl.actionDescriptions.HW_GPU_TUNING');
        case 'PLUGIN_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.PLUGIN_ADMIN');
        case 'FACTORY_RESET':
            return i18n.t('settings.acl.actionDescriptions.FACTORY_RESET');
        case 'METRICS_RESET':
            return i18n.t('settings.acl.actionDescriptions.METRICS_RESET');
        case 'REQUEST_CANCELLATION_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.REQUEST_CANCELLATION_ADMIN');
        case 'SYSTEM_POWER':
            return i18n.t('settings.acl.actionDescriptions.SYSTEM_POWER');
        case 'MODEL_READ':
            return i18n.t('settings.acl.actionDescriptions.MODEL_READ');
        case 'MODEL_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.MODEL_ADMIN');
        case 'MODEL_ROUTING_READ':
            return i18n.t('settings.acl.actionDescriptions.MODEL_ROUTING_READ');
        case 'MODEL_ROUTING_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.MODEL_ROUTING_ADMIN');
        case 'NOTIFICATIONS':
            return i18n.t('settings.acl.actionDescriptions.NOTIFICATIONS');
        case 'SOFTWARE_UPDATE':
            return i18n.t('settings.acl.actionDescriptions.SOFTWARE_UPDATE');
        case 'LOG_ACCESS':
            return i18n.t('settings.acl.actionDescriptions.LOG_ACCESS');
        case 'ACL_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.ACL_ADMIN');
        case 'SYSTEM_STATUS_READ':
            return i18n.t('settings.acl.actionDescriptions.SYSTEM_STATUS_READ');
        case 'PLUGIN_READ':
            return i18n.t('settings.acl.actionDescriptions.PLUGIN_READ');
        case 'HARDWARE_READ':
            return i18n.t('settings.acl.actionDescriptions.HARDWARE_READ');
        case 'SEARCH_READ':
            return i18n.t('settings.acl.actionDescriptions.SEARCH_READ');
        case 'OPENAI_API':
            return i18n.t('settings.acl.actionDescriptions.OPENAI_API');
        case 'WEBUI_APPEARANCE_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.WEBUI_APPEARANCE_ADMIN');
        case 'OPENAI_API_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.OPENAI_API_ADMIN');
        case 'FILE_EXPLORER_READ':
            return i18n.t('settings.acl.actionDescriptions.FILE_EXPLORER_READ');
        case 'FILE_EXPLORER_WRITE':
            return i18n.t('settings.acl.actionDescriptions.FILE_EXPLORER_WRITE');
        case 'FILE_EXPLORER_HASH':
            return i18n.t('settings.acl.actionDescriptions.FILE_EXPLORER_HASH');
        case 'FILE_EXPLORER_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.FILE_EXPLORER_ADMIN');
        case 'HOST_MANAGEMENT_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.HOST_MANAGEMENT_ADMIN');
        case 'MCP_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.MCP_ADMIN');
        case 'TASK_MANAGEMENT':
            return i18n.t('settings.acl.actionDescriptions.TASK_MANAGEMENT');
        case 'HW_PROCESS_VIEW':
            return i18n.t('settings.acl.actionDescriptions.HW_PROCESS_VIEW');
        case 'BACKUP_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.BACKUP_ADMIN');
        case 'WEB_SEARCH':
            return i18n.t('settings.acl.actionDescriptions.WEB_SEARCH');
        case 'RAG_USE':
            return i18n.t('settings.acl.actionDescriptions.RAG_USE');
        case 'MCP_USE':
            return i18n.t('settings.acl.actionDescriptions.MCP_USE');
        case 'LICENSING_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.LICENSING_ADMIN');
        case 'RECOVERY_ADMIN':
            return i18n.t('settings.acl.actionDescriptions.RECOVERY_ADMIN');
        default:
            throw new Error(`ACL action description mapping missing for "${action}"`);
    }
};

export { resolveAclActionDescription, resolveAclActionLabel };
