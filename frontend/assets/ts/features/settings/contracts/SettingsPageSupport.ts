/* SoAI - Settings feature page support [frontend/assets/ts/features/settings/contracts/SettingsPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { BackupApiEntry, BackupEntry, NormalTabDefinition } from '@core/settings/contracts.ts';

const PAGE_ID = 'settings';

const PAGE_MODULE_ID = 'pages.SettingsPage';

const UI_IDS = Object.freeze({
    TAB_CONTAINER: 'settings-tabs-container',
    CONTENT: 'settings-content',
    LOADING: 'settings-loading',
    SAVE_BUTTON: 'saveBtn',
    ADVANCED_TOGGLE_BTN: 'advanced-mode-toggle-btn',
    EMPTY_STATE: 'settings-empty',
    SEARCH_CONTAINER: 'settings-search-container',
    PROMPT_ENHANCER_MODEL_SETTING: 'prompt-enhancer-model-setting',
    PROMPT_ENHANCER_MODEL_SELECT: 'prompt-enhancer-model-select',
    REGIONAL_LOCALE_SELECT: 'regional-locale-select',
    DATE_FORMAT_SELECT: 'date-format-select',
    MEASUREMENT_UNITS_SELECT: 'measurement-units-select',
    NOTIFICATION_DURATION_SLIDER: 'notification-duration-slider',
    NOTIFICATION_DURATION_VALUE: 'notification-duration-value',
    INTERFACE_SCALE_SLIDER: 'interface-scale-slider',
    INTERFACE_SCALE_VALUE: 'interface-scale-value',
    HEADER_CLOCK_TOGGLE: 'header-clock-toggle',
    CLOCK_SECONDS_TOGGLE: 'clock-seconds-toggle',
    CODE_RECOGNITION_TOGGLE: 'code-recognition-toggle',
    WALLPAPER_PREVIEW: 'wallpaper-preview',
    WALLPAPER_OVERLAY_SLIDER: 'wallpaper-overlay-slider',
    WALLPAPER_OVERLAY_VALUE: 'wallpaper-overlay-value',
    WALLPAPER_INFO: 'wallpaper-info',
    WALLPAPER_UPLOAD: 'wallpaper-upload-btn',
    WALLPAPER_DOWNLOAD: 'wallpaper-download-btn',
    WALLPAPER_URL: 'wallpaper-url-input',
    WALLPAPER_FILE: 'wallpaper-file-input',
    SOLID_BACKGROUND_CONTAINER: 'solid-background-container',
    SOLID_BACKGROUND_PICKER: 'solid-background-color-picker',
    SOLID_BACKGROUND_CLEAR: 'solid-background-clear-btn',
    ACCENT_COLOR_PICKER: 'accent-color-picker',
    ACCENT_COLOR_CLEAR: 'accent-color-clear-btn',
    SURFACE_COLOR_PICKER: 'surface-color-picker',
    SURFACE_COLOR_CLEAR: 'surface-color-clear-btn',
    NO_WALLPAPER_MESSAGE: 'no-wallpaper-message',
    SIDEBAR_EDIT_BTN: 'sidebar-customize-edit-btn',
    SIDEBAR_CHECKBOXES_CONTAINER: 'sidebar-page-checkboxes',
    DASHBOARD_EDIT_BTN: 'dashboard-customize-edit-btn',
    DASHBOARD_CHECKBOXES_CONTAINER: 'dashboard-element-checkboxes',
    MCP_REFRESH: 'mcp-refresh-btn',
    MCP_SERVER_ADD: 'mcp-server-add-btn',
    MCP_SERVER_LIST: 'mcp-servers-list',
    MCP_CONNECTION_LIST: 'mcp-connections-list',
    MCP_SEARCH_PROVIDER_SELECT: 'mcp-search-provider-select',
    MCP_SEARCH_LIST: 'mcp-search-keys-list',
    MCP_ROOT_CANCEL: 'mcp-root-cancel-btn',
    MCP_ROOT_LIST: 'mcp-roots-list',
    MCP_INTERACTIONS_LIST: 'mcp-interactions-list',
    MCP_ACCESS_TOKEN_CREATE: 'mcp-access-token-create-btn',
    BACKUP_CREATE: 'backup-create-btn',
    BACKUP_LIST: 'backup-list',
    BACKUP_PROGRESS: 'settings-backup-progress'
});

const MCP_SEARCH_PROVIDER_CUSTOM = '__custom__';

const NORMAL_TAB_DEFINITIONS: readonly NormalTabDefinition[] = Object.freeze([
    { id: 'general', getLabel: () => i18n.t('settings.tabs.preferences'), rendererId: 'preferences' },
    { id: 'theme', getLabel: () => i18n.t('settings.tabs.theme'), rendererId: 'theme' },
    { id: 'users', getLabel: () => i18n.t('settings.tabs.users'), rendererId: 'users', adminOnly: true, actions: ['USER_ADMIN'] },
    { id: 'security', getLabel: () => i18n.t('settings.tabs.security'), rendererId: 'security', adminOnly: true, actions: ['CONFIG_PATCH', 'ACL_ADMIN'] },
    { id: 'licensing', getLabel: () => i18n.t('settings.tabs.licensing'), rendererId: 'licensing', adminOnly: true, actions: ['LICENSING_ADMIN'] },
    { id: 'acl', getLabel: () => i18n.t('settings.tabs.acl'), rendererId: 'acl', adminOnly: true, actions: ['ACL_ADMIN'] },
    { id: 'api-keys', getLabel: () => i18n.t('settings.tabs.apiKeys'), rendererId: 'apiKeys', adminOnly: true, actions: ['OPENAI_API_ADMIN'] },
    { id: 'mcp', getLabel: () => i18n.t('settings.tabs.mcp'), rendererId: 'mcp', adminOnly: true, actions: ['MCP_ADMIN'] },
    { id: 'external-accounts', getLabel: () => i18n.t('settings.tabs.externalAccounts'), rendererId: 'externalAccounts' },
    { id: 'messaging', getLabel: () => i18n.t('settings.tabs.messaging'), rendererId: 'messaging', actions: ['OPENAI_API', 'MCP_USE', 'MODEL_READ'] },
    { id: 'backup', getLabel: () => i18n.t('settings.tabs.backup'), rendererId: 'backup', adminOnly: true, actions: ['BACKUP_ADMIN'] },
    { id: 'reset', getLabel: () => i18n.t('settings.tabs.reset'), rendererId: 'system', adminOnly: true }
]);

const composeNormalTabDefinitions = (productTabs: readonly NormalTabDefinition[] = []): readonly NormalTabDefinition[] => {
    const resetTab = NORMAL_TAB_DEFINITIONS.find((definition) => definition.id === 'reset');
    if (!resetTab) {
        throw new Error('Settings reset tab definition is required');
    }
    return Object.freeze([...NORMAL_TAB_DEFINITIONS.filter((definition) => definition.id !== resetTab.id), ...productTabs, resetTab]);
};

function transformBackupEntry(raw: BackupApiEntry): BackupEntry {
    const targetsCompleted = raw.targetsCompleted;
    const hasCompletedTargets = Object.keys(targetsCompleted).length > 0;
    return {
        backupId: raw.backupId,
        createdAt: raw.timestampMs,
        sizeBytes: raw.totalSizeBytes,
        valid: hasCompletedTargets && raw.licensingRecoveryState !== 'incomplete',
        licensingRecoveryState: raw.licensingRecoveryState
    };
}

export { PAGE_ID, PAGE_MODULE_ID, UI_IDS, MCP_SEARCH_PROVIDER_CUSTOM, NORMAL_TAB_DEFINITIONS, composeNormalTabDefinitions, transformBackupEntry };
