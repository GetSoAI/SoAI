/* SoAI - Settings page normal tab rendering [frontend/assets/ts/pages/settings/controllers/page/normalTabRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NormalTabDefinition } from '@core/settings/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const renderNormalTabContent = (state: SettingsPageState, definition: NormalTabDefinition): string => {
    switch (definition.rendererId) {
        case 'preferences': {
            const manager = state.preferencesManager;
            if (!manager) throw new Error('PreferencesManager not initialized');
            const identityContent = state.instanceIdentityManager?.render().html ?? '';
            return manager.render(identityContent).html;
        }
        case 'theme': {
            const manager = state.themeManager;
            if (!manager) throw new Error('ThemeManager not initialized');
            return manager.render().html;
        }
        case 'users': {
            const manager = state.usersManager;
            if (!manager) throw new Error('UsersManager not initialized');
            return manager.render().html;
        }
        case 'security': {
            const manager = state.securityManager;
            if (!manager) throw new Error('SecurityManager not initialized');
            return manager.render().html;
        }
        case 'licensing': {
            const manager = state.licensingManager;
            if (!manager) throw new Error('LicensingManager not initialized');
            return manager.render().html;
        }
        case 'acl': {
            const manager = state.aclManager;
            if (!manager) throw new Error('AclManager not initialized');
            return manager.render().html;
        }
        case 'apiKeys': {
            const manager = state.apiKeysManager;
            if (!manager) throw new Error('ApiKeysManager not initialized');
            return manager.render().html;
        }
        case 'mcp': {
            const manager = state.mcpManager;
            if (!manager) throw new Error('McpManager not initialized');
            return manager.render().html;
        }
        case 'externalAccounts': {
            const manager = state.externalAccountsManager;
            if (!manager) throw new Error('ExternalAccountsManager not initialized');
            return manager.render().html;
        }
        case 'messaging': {
            const manager = state.messagingManager;
            if (!manager) throw new Error('MessagingManager not initialized');
            return manager.render().html;
        }
        case 'backup': {
            const manager = state.backupManager;
            if (!manager) throw new Error('BackupManager not initialized');
            return manager.render().html;
        }
        case 'product': {
            const manager = state.productManagers.get(definition.id);
            if (!manager) throw new Error(`Product settings manager is not initialized for tab: ${definition.id}`);
            return manager.render().html;
        }
        case 'system': {
            const manager = state.systemManager;
            if (!manager) throw new Error('SystemManager not initialized');
            return manager.render().html;
        }
    }
};

export { renderNormalTabContent };
