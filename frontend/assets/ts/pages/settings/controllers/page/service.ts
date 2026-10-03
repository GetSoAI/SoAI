/* SoAI - Settings page service [frontend/assets/ts/pages/settings/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { UI_IDS, createAdvancedSettingsRenderer, markSettingsCapabilityFailed, markSettingsCapabilityReady, markSettingsCapabilityRefreshing, settleSettingsCapability } from '@features/settings/public.ts';
import { canManageInstanceIdentity, hasSettingsAction, isSettingsNormalTabVisibleById, refreshAccessState } from '@pages/settings/controllers/page/settingsAccessController.ts';
import { createCoreSettingsManagers } from '@pages/settings/controllers/page/adapters.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { createAdminSettingsManagers } from '@pages/settings/controllers/page/effects.ts';
import { createUiPrefsSnapshot } from '@pages/settings/controllers/page/loadDataMappers.ts';
import { updateSecurityTabNotifyBadge } from '@pages/settings/controllers/page/securityTabBadgeController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

interface SettingsDataCallbacks extends SettingsManagerCallbacks {
    createAllTabs: () => Promise<void>;
    renderAllContent: () => void;
}
const requestInstanceIdentity = (page: SettingsRuntimeContext, state: SettingsPageState, requestOptions: ReturnType<typeof buildSignalRequestOptions>) => {
    return canManageInstanceIdentity(page, state) ? page.owners.api.system.health(requestOptions) : Promise.resolve(null);
};
const getElement = (page: SettingsRuntimeContext, state: SettingsPageState, id: string): Element | null => {
    if (!id) {
        return null;
    }
    const cached = state.uiCache.get(id);
    if (cached && document.contains(cached)) {
        return cached;
    }
    state.uiCache.delete(id);
    const found = page.owners.pageDom.optional(id);
    if (found) {
        state.uiCache.set(id, found);
    }
    return found;
};
const resetElementCache = (state: SettingsPageState): void => {
    state.uiCache.clear();
};

const initializeManagers = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    createCoreSettingsManagers(page, state, callbacks);
    createAdminSettingsManagers(page, state, callbacks);
};

const setupManagersEventListeners = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    if (!state.preferencesManager || !state.themeManager) {
        throw new Error('Settings managers are not initialized');
    }
    state.preferencesManager.setupEventListeners();
    state.instanceIdentityManager?.setupEventListeners();
    state.themeManager.setupEventListeners();
    if (!state.externalAccountsManager) {
        throw new Error('ExternalAccountsManager not initialized');
    }
    state.externalAccountsManager.setupEventListeners();
    if (isSettingsNormalTabVisibleById(page, state, 'messaging')) {
        if (!state.messagingManager) throw new Error('MessagingManager not initialized');
        state.messagingManager.setupEventListeners();
    }
    if (isSettingsNormalTabVisibleById(page, state, 'connect')) {
        if (!state.connectManager) throw new Error('ConnectManager not initialized');
        state.connectManager.setupEventListeners();
    }

    if (isSettingsNormalTabVisibleById(page, state, 'users')) {
        if (!state.usersManager) {
            throw new Error('UsersManager not initialized');
        }
        state.usersManager.setupEventListeners();
    }
    if (page.owners.auth.isAdmin()) {
        if (isSettingsNormalTabVisibleById(page, state, 'security')) {
            if (!state.securityManager) {
                throw new Error('SecurityManager not initialized');
            }
            state.securityManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'licensing')) {
            if (!state.licensingManager) throw new Error('LicensingManager not initialized');
            state.licensingManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'mcp')) {
            if (!state.mcpManager) {
                throw new Error('McpManager not initialized');
            }
            state.mcpManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'reset')) {
            if (!state.systemManager) {
                throw new Error('SystemManager not initialized');
            }
            state.systemManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'acl')) {
            if (!state.aclManager) {
                throw new Error('AclManager not initialized');
            }
            state.aclManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'api-keys')) {
            if (!state.apiKeysManager) {
                throw new Error('ApiKeysManager not initialized');
            }
            state.apiKeysManager.setupEventListeners();
        }
        if (isSettingsNormalTabVisibleById(page, state, 'backup')) {
            if (!state.backupManager) {
                throw new Error('BackupManager not initialized');
            }
            state.backupManager.setupEventListeners();
        }
        if (state.productSettingsEnabled) {
            for (const [tabId, manager] of state.productManagers) {
                if (isSettingsNormalTabVisibleById(page, state, tabId)) {
                    manager.setupEventListeners();
                }
            }
        }
    }
    syncSettingsSectionActivity(state, state.currentSection);
};

const syncSettingsSectionActivity = (state: SettingsPageState, activeTab: string): void => {
    state.apiKeysManager?.setSectionActive(activeTab === 'api-keys');
    state.mcpManager?.setSectionActive(activeTab === 'mcp');
};

const disposeManagers = (state: SettingsPageState): void => {
    state.productManagers.forEach((manager) => manager.dispose());
    state.backupManager?.dispose();
    state.messagingManager?.dispose();
    state.mcpManager?.dispose();
    state.securityManager?.dispose();
    state.licensingManager?.dispose();
    state.connectManager?.dispose();
    state.externalAccountsManager?.dispose();
    state.apiKeysManager?.dispose();
    state.aclManager?.dispose();
    state.themeManager?.dispose();
    state.preferencesManager?.dispose();
    state.instanceIdentityManager?.dispose();
    state.systemManager?.dispose();
    state.usersManager?.dispose();
    state.preferencesManager = null;
    state.instanceIdentityManager = null;
    state.themeManager = null;
    state.usersManager = null;
    state.aclManager = null;
    state.apiKeysManager = null;
    state.securityManager = null;
    state.licensingManager = null;
    state.connectManager = null;
    state.mcpManager = null;
    state.externalAccountsManager = null;
    state.messagingManager = null;
    state.backupManager = null;
    state.systemManager = null;
    state.productManagers = new Map();
};

const resolveAdvancedRenderer = (state: SettingsPageState) => {
    if (state.advancedRenderer) {
        return state.advancedRenderer;
    }
    state.advancedRenderer = createAdvancedSettingsRenderer({
        excludeSections: new Set<string>()
    });
    return state.advancedRenderer;
};

const loadData = async (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsDataCallbacks, options: { signal?: AbortSignal | null; refreshAccess?: boolean } = {}): Promise<void> => {
    const signal = options.signal ?? null;
    const requestOptions = signal ? buildSignalRequestOptions({ signal }) : buildSignalRequestOptions();
    const content = getElement(page, state, UI_IDS.CONTENT);
    if (content) {
        page.owners.pageDom.addClass(content, 'is-loading');
        setAriaBusy(content, true);
    }
    try {
        throwIfAborted(signal);
        await page.owners.storage.ready;
        throwIfAborted(signal);
        if (options.refreshAccess !== false) {
            await refreshAccessState(page, state, signal);
        }
        throwIfAborted(signal);
        const currentUser = page.owners.auth.getCurrentUser();
        state.currentUserId = currentUser?.id != null ? String(currentUser.id) : null;

        const isAdmin = page.owners.auth.isAdmin();
        const canReadCoreConfig = hasSettingsAction(state, 'CONFIG_PATCH');
        const emptyCoreConfig: JsonObject = {};
        const coreConfigRequest = canReadCoreConfig ? page.owners.api.configs.get('core', requestOptions) : Promise.resolve(emptyCoreConfig);
        const instanceIdentityRequest = requestInstanceIdentity(page, state, requestOptions);
        const usersVisible = isSettingsNormalTabVisibleById(page, state, 'users');
        const usersResultRequest = usersVisible && isAdmin && hasSettingsAction(state, 'USER_ADMIN') ? settleSettingsCapability(() => page.owners.api.webui.users.list(requestOptions)) : null;
        const aclPolicyResultRequest = isAdmin && hasSettingsAction(state, 'ACL_ADMIN') ? settleSettingsCapability(() => page.owners.api.webui.acl.getPolicy(requestOptions)) : null;
        if (isSettingsNormalTabVisibleById(page, state, 'security')) {
            state.securityAvailability = markSettingsCapabilityRefreshing(state.securityAvailability);
        }
        const [coreConfig, instanceIdentity, usersResult, aclPolicyResult] = await Promise.all([coreConfigRequest, instanceIdentityRequest, usersResultRequest, aclPolicyResultRequest]);
        throwIfAborted(signal);
        if (!isPlainObject(coreConfig)) {
            throw new TypeError('SettingsPage expects core config response to be an object');
        }
        state.coreConfig = toJsonCompatibleObject(coreConfig);
        state.instanceIdentity = instanceIdentity;
        if (usersResult?.succeeded && usersResult.value) {
            state.users = usersResult.value;
            state.usersAvailability = markSettingsCapabilityReady();
        } else if (usersResult) {
            state.usersAvailability = markSettingsCapabilityFailed(state.usersAvailability);
            if (usersResult.error) page.owners.feedback.handle(usersResult.error, 'Settings users load');
        } else {
            state.users = [];
        }
        if (aclPolicyResult?.succeeded) {
            state.aclPolicy = aclPolicyResult.value;
            state.aclAvailability = markSettingsCapabilityReady();
        } else if (aclPolicyResult) {
            state.aclAvailability = markSettingsCapabilityFailed(state.aclAvailability);
            if (aclPolicyResult.error) page.owners.feedback.handle(aclPolicyResult.error, 'Settings ACL load');
        }
        state.uiPrefsManager = page.owners.services.createConfigurationManager();
        state.uiPrefsManager.initialize(createUiPrefsSnapshot(page));
        state.uiPrefsManager.onChange(() => callbacks.notifySaveChanged());

        initializeManagers(page, state, callbacks);
        throwIfAborted(signal);
        state.configManager = page.owners.services.createConfigurationManager();
        if (state.configManager) {
            state.configManager.initialize(state.coreConfig);
            state.configManager.onChange(() => callbacks.notifySaveChanged());
        }

        await callbacks.createAllTabs();
        throwIfAborted(signal);
        callbacks.renderAllContent();
        callbacks.rebindConfigForm();
        callbacks.notifySaveChanged();
        updateSecurityTabNotifyBadge(page, state);
    } finally {
        if (content && !signal?.aborted) {
            page.owners.pageDom.removeClass(content, 'is-loading');
            setAriaBusy(content, false);
        }
    }
};

export { disposeManagers, getElement, loadData, requestInstanceIdentity, resetElementCache, resolveAdvancedRenderer, setupManagersEventListeners, syncSettingsSectionActivity };
