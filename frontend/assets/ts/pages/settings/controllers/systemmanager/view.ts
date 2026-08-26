/* SoAI - Settings page system manager rendering [frontend/assets/ts/pages/settings/controllers/systemmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { renderSection, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { SETTINGS_SYSTEM_CLEAR_PROMPT_HISTORY_ACTION, SETTINGS_SYSTEM_DELETE_ALL_CONVERSATIONS_ACTION, SETTINGS_SYSTEM_FACTORY_RESET_ACTION, SETTINGS_SYSTEM_RESET_ACL_POLICY_ACTION, SETTINGS_SYSTEM_RESET_APPEARANCE_ACTION, SETTINGS_SYSTEM_RESET_CHAT_PRESETS_ACTION, SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION, SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION, SETTINGS_SYSTEM_RESET_METRICS_ACTION, SETTINGS_SYSTEM_RESET_PAGE_LAYOUTS_ACTION, SETTINGS_SYSTEM_RESET_PASSWORD_MANAGER_ACTION, SETTINGS_SYSTEM_RESET_PREFERENCES_ACTION, SETTINGS_SYSTEM_RESET_RECENT_SEARCHES_ACTION, SETTINGS_SYSTEM_RESET_TOOL_APPROVAL_PERMISSIONS_ACTION } from '@pages/settings/controllers/systemmanager/constants.ts';
import type { SystemActionConfig } from '@pages/settings/controllers/systemmanager/contracts.ts';

const createSystemActionConfigs = (): SystemActionConfig[] => {
    return [
        {
            id: 'acl-policy-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_ACL_POLICY_ACTION,
            enabled: true,
            title: i18n.t('settings.system.aclPolicyReset.title'),
            description: i18n.t('settings.system.aclPolicyReset.description')
        },
        {
            id: 'appearance-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_APPEARANCE_ACTION,
            enabled: true,
            title: i18n.t('settings.system.appearanceReset.title'),
            description: i18n.t('settings.system.appearanceReset.description')
        },
        {
            id: 'metrics-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_METRICS_ACTION,
            enabled: true,
            title: i18n.t('settings.system.metricsReset.title'),
            description: i18n.t('settings.system.metricsReset.description')
        },
        {
            id: 'hardware-history-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION,
            enabled: true,
            title: i18n.t('settings.system.hardwareHistoryReset.title'),
            description: i18n.t('settings.system.hardwareHistoryReset.description')
        },
        {
            id: 'page-layouts-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_PAGE_LAYOUTS_ACTION,
            enabled: true,
            title: i18n.t('settings.system.pageLayoutsReset.title'),
            description: i18n.t('settings.system.pageLayoutsReset.description')
        },
        {
            id: 'preferences-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_PREFERENCES_ACTION,
            enabled: true,
            title: i18n.t('settings.system.preferencesReset.title'),
            description: i18n.t('settings.system.preferencesReset.description')
        },
        {
            id: 'chat-presets-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_CHAT_PRESETS_ACTION,
            enabled: true,
            title: i18n.t('settings.system.chatPresetsReset.title'),
            description: i18n.t('settings.system.chatPresetsReset.description')
        },
        {
            id: 'prompt-history-clear-btn',
            actionId: SETTINGS_SYSTEM_CLEAR_PROMPT_HISTORY_ACTION,
            enabled: true,
            title: i18n.t('settings.system.promptHistoryClear.title'),
            description: i18n.t('settings.system.promptHistoryClear.description'),
            buttonLabel: i18n.t('settings.system.promptHistoryClear.button')
        },
        {
            id: 'recent-searches-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_RECENT_SEARCHES_ACTION,
            enabled: true,
            title: i18n.t('settings.system.recentSearchesReset.title'),
            description: i18n.t('settings.system.recentSearchesReset.description')
        },
        {
            id: 'tool-approval-permissions-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_TOOL_APPROVAL_PERMISSIONS_ACTION,
            enabled: true,
            title: i18n.t('settings.system.toolApprovalPermissionsReset.title'),
            description: i18n.t('settings.system.toolApprovalPermissionsReset.description')
        },
        {
            id: 'password-manager-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_PASSWORD_MANAGER_ACTION,
            enabled: true,
            title: i18n.t('settings.system.passwordManagerReset.title'),
            description: i18n.t('settings.system.passwordManagerReset.description')
        },
        {
            id: 'conversations-delete-all-btn',
            actionId: SETTINGS_SYSTEM_DELETE_ALL_CONVERSATIONS_ACTION,
            enabled: true,
            title: i18n.t('settings.system.deleteAllConversations.title'),
            description: i18n.t('settings.system.deleteAllConversations.description')
        },
        {
            id: 'configuration-reset-btn',
            actionId: SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION,
            enabled: true,
            title: i18n.t('settings.system.configurationReset.title'),
            description: i18n.t('settings.system.configurationReset.description')
        },
        {
            id: 'factory-reset-btn',
            actionId: SETTINGS_SYSTEM_FACTORY_RESET_ACTION,
            enabled: true,
            title: i18n.t('settings.system.factoryReset.title'),
            description: i18n.t('settings.system.factoryReset.description'),
            buttonLabel: i18n.t('settings.system.factoryReset.button'),
            className: 'setting-item--danger'
        }
    ];
};

const resolveActionButtonLabel = (actionConfig: SystemActionConfig, resetLabel: string): string => {
    if (actionConfig.buttonLabel) {
        return actionConfig.buttonLabel;
    }
    return resetLabel;
};

const renderSystemActionButton = (action: SystemActionConfig, resetLabel: string): string => {
    const disabledAttributes = renderControlDisabledAttributes(!action.enabled);
    const buttonLabel = resolveActionButtonLabel(action, resetLabel);
    return `<button type="button" id="${action.id}" data-action="${action.actionId}" class="ui-button ui-button--sm ui-variant-danger" ${disabledAttributes} ${renderLabelAttributes(action.title)}>${buttonLabel}</button>`;
};

const renderSystemManagerSection = (canRunSystemAction: (action: SystemActionConfig['actionId']) => boolean): string => {
    const resetLabel = i18n.t('settings.system.resetButtonLabel');
    const actions = createSystemActionConfigs().filter((action) => canRunSystemAction(action.actionId));
    const items = actions.map((action) =>
        renderSettingItem({
            label: action.title,
            help: !action.enabled && action.unsupported ? `${action.description} ${action.unsupported}` : action.description,
            className: `setting-item--system${action.className ? ` ${action.className}` : ''}`,
            control: renderSystemActionButton(action, resetLabel)
        })
    );
    return renderSection({
        title: i18n.t('settings.system.sectionTitle'),
        description: i18n.t('settings.system.sectionDescription'),
        className: 'settings-section--system',
        content: renderSettingsSubgroup({
            title: i18n.t('settings.system.subgroupTitle'),
            description: i18n.t('settings.system.subgroupDescription'),
            content: renderSettingsGroup(items)
        })
    });
};

export { renderSystemManagerSection };
