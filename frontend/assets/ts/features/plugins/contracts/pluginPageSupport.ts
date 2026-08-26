/* SoAI - Plugins feature plugin page support [frontend/assets/ts/features/plugins/contracts/pluginPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL, MODELS_ACTION_MANAGE_PROVIDERS } from '@core/models/pageActions.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@core/plugins/providerMode.ts';
import { PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_INSTALL_ERROR } from '@core/state/pluginStatus.ts';
import { isObject } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { PLUGINS_ACTION_CLONE_PLUGIN, PLUGINS_ACTION_DELETE_PLUGIN, PLUGINS_ACTION_DISABLE_OVERRIDE, PLUGINS_ACTION_EDIT_CONFIG, PLUGINS_ACTION_ENABLE_OVERRIDE, PLUGINS_ACTION_INSTALL_BACKEND, PLUGINS_ACTION_MANAGE_BACKEND, PLUGINS_ACTION_OPEN_PLUGIN, PLUGINS_ACTION_STOP_PLUGIN, PLUGINS_ACTION_TOGGLE_ENABLED } from '@features/plugins/contracts/pluginActionIds.ts';

interface DisableControlHost {
    updateProperty(element: Element, property: string, value: DomPropertyValue): void;
    toggleClassName(element: Element, className: string, force: boolean): void;
}

interface PluginActionPresentationPort {
    updateProperty: DisableControlHost['updateProperty'];
    toggleClassName: DisableControlHost['toggleClassName'];
    dom: {
        getData(element: Element, key: string): string | null;
    };
    formatPluginName(name: string): string;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
}

interface PluginActionPolicyPort {
    deletePlugin(name: string): void;
    prepareConfigModal(plugin: PluginRecord): void;
    isHardwareIncompatible(plugin: PluginRecord): boolean;
    canExecutePluginAction(plugin: PluginRecord, options?: { notify?: boolean | undefined; allowCompatibilityOverride?: boolean | undefined }): boolean;
    setCompatibilityOverride(plugin: PluginRecord, override: boolean, event?: Event): void;
    isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    isCircuitBreakerActive(plugin: PluginRecord): boolean;
    getPluginStatus(plugin: PluginRecord): string;
    resolvePluginRecord(plugin: PluginRecord): PluginRecord | null;
    getProviderCount(record: PluginRecord): number;
}

interface PluginLifecycleActions {
    resetCircuitBreaker(plugin: PluginRecord, event?: Event): void;
    togglePluginEnabled(plugin: PluginRecord, event?: Event): void;
    stopPlugin(plugin: PluginRecord): void;
}

interface PluginNavigationActions {
    openInstallBackendModal(plugin: PluginRecord): void;
    openDownloadModelModal(plugin: PluginRecord): void;
    openAddProviderModal(plugin: PluginRecord): void;
    openCloneModal(plugin: PluginRecord): void;
    openManageBackendModal(plugin: PluginRecord): void;
    navigateToModels(action: string, record: PluginRecord): boolean;
    openPluginInfoModal(plugin: PluginRecord): void;
}

interface PluginActionHost {
    presentation: PluginActionPresentationPort;
    policy: PluginActionPolicyPort;
    lifecycle: PluginLifecycleActions;
    navigation: PluginNavigationActions;
}

const C_HIDDEN = 'u-hidden';
const C_DISABLED = 'is-disabled';
const C_CLICK = 'click';
const PLUGIN_FILTER_ACTIVE = 'active';

const CONCURRENT_PLUGINS_SLIDER: Readonly<{ MIN: number; DEFAULT_MAX: number; MAX_LIMIT: number }> = Object.freeze({
    MIN: 1,
    DEFAULT_MAX: 100,
    MAX_LIMIT: 1000
});

const setElementDisabledState = (host: DisableControlHost, element: Element, disabled: boolean, disabledClassName: string): void => {
    host.updateProperty(element, 'disabled', disabled);
    host.toggleClassName(element, disabledClassName, disabled);
};

const supportsBackendInstallation = (plugin: PluginRecord): boolean => {
    if (!isObject(plugin.capabilities)) {
        return true;
    }
    return plugin.capabilities.supportsBackendInstallation !== false;
};

const shouldOpenInstallBackendModal = (host: PluginActionHost, plugin: PluginRecord): boolean => {
    if (host.policy.isPluginPermanentlyDisabled(plugin) || host.policy.isHardwareIncompatible(plugin) || host.policy.isCircuitBreakerActive(plugin) || !supportsBackendInstallation(plugin)) {
        return false;
    }
    const status = host.policy.getPluginStatus(plugin);
    return status === PLUGIN_STATUS_BACKEND_NOT_INSTALLED || status === PLUGIN_STATUS_INSTALL_ERROR;
};

const openBackendManagementSurface = (host: PluginActionHost, plugin: PluginRecord, backendStatus: string | null): void => {
    if (backendStatus === PLUGIN_STATUS_BACKEND_NOT_INSTALLED) {
        host.navigation.openInstallBackendModal(plugin);
        return;
    }
    if (backendStatus === PLUGIN_STATUS_INCOMPATIBLE) {
        host.policy.notifyPluginIncompatible(plugin);
        return;
    }
    host.navigation.openManageBackendModal(plugin);
};

const PLUGIN_ACTION_HANDLERS: Readonly<Record<string, (host: PluginActionHost, plugin: PluginRecord, event?: Event) => void>> = Object.freeze({
    [PLUGINS_ACTION_OPEN_PLUGIN]: (host, plugin) => {
        if (shouldOpenInstallBackendModal(host, plugin)) {
            host.navigation.openInstallBackendModal(plugin);
        } else {
            host.navigation.openPluginInfoModal(plugin);
        }
    },
    [PLUGINS_ACTION_DELETE_PLUGIN]: (host, plugin) => plugin?.name && host.policy.deletePlugin(plugin.name),
    [PLUGINS_ACTION_EDIT_CONFIG]: (host, plugin) => host.policy.prepareConfigModal(plugin),
    [PLUGINS_ACTION_ENABLE_OVERRIDE]: (host, plugin, event) => host.policy.setCompatibilityOverride(plugin, true, event),
    [PLUGINS_ACTION_DISABLE_OVERRIDE]: (host, plugin, event) => host.policy.setCompatibilityOverride(plugin, false, event),
    [PLUGINS_ACTION_TOGGLE_ENABLED]: (host, plugin, event) => {
        const allowOverride = host.policy.isHardwareIncompatible(plugin) === true;
        if (!host.policy.canExecutePluginAction(plugin, { notify: false, allowCompatibilityOverride: allowOverride })) {
            if (host.policy.isPluginPermanentlyDisabled(plugin)) host.policy.notifyPluginIncompatible(plugin);
            return;
        }
        if (host.policy.isCircuitBreakerActive(plugin)) {
            host.lifecycle.resetCircuitBreaker(plugin, event);
        } else {
            host.lifecycle.togglePluginEnabled(plugin, event);
        }
    },
    [PLUGINS_ACTION_STOP_PLUGIN]: (host, plugin) => host.lifecycle.stopPlugin(plugin),
    [PLUGINS_ACTION_INSTALL_BACKEND]: (host, plugin) => host.navigation.openInstallBackendModal(plugin),
    [PLUGINS_ACTION_MANAGE_BACKEND]: (host, plugin) => openBackendManagementSurface(host, plugin, host.policy.getPluginStatus(plugin)),
    [MODELS_ACTION_DOWNLOAD_MODEL]: (host, plugin) => host.navigation.openDownloadModelModal(plugin),
    [MODELS_ACTION_ADD_PROVIDER]: (host, plugin) => host.navigation.openAddProviderModal(plugin),
    [PLUGINS_ACTION_CLONE_PLUGIN]: (host, plugin) => host.navigation.openCloneModal(plugin)
});

const METRIC_BADGE_HANDLERS: Readonly<Record<string, (host: PluginActionHost, plugin: PluginRecord, target: Element, badgeElement: Element) => boolean>> = Object.freeze({
    BACKEND: (host, plugin, _target, badgeElement) => {
        openBackendManagementSurface(host, plugin, host.presentation.dom.getData(badgeElement, 'status'));
        return true;
    },
    PROVIDERS: (host, plugin) => {
        const record = host.policy.resolvePluginRecord(plugin);
        if (!record) return false;
        const providerMode = resolveProviderMode(record);
        if (providerMode !== PROVIDER_MODE.USER_MANAGED) {
            const rawName = String(record.displayName ?? record.name ?? '').trim();
            const displayName = rawName ? host.presentation.formatPluginName(rawName) || rawName : i18n.t('common.unknown');
            if (providerMode === PROVIDER_MODE.PLUGIN_MANAGED) {
                host.presentation.showNotification(i18n.t('plugins.notifications.providerManagedReadOnly', { plugin: displayName }), 'info');
            } else {
                host.presentation.showNotification(i18n.t('plugins.notifications.providersUnavailable', { plugin: displayName }), 'info');
            }
            return false;
        }
        const action = host.policy.getProviderCount(record) === 0 ? MODELS_ACTION_ADD_PROVIDER : MODELS_ACTION_MANAGE_PROVIDERS;
        return host.navigation.navigateToModels(action, record);
    },
    VERSION: (host, plugin) => {
        host.navigation.openPluginInfoModal(plugin);
        return true;
    }
});

export { C_CLICK, C_DISABLED, C_HIDDEN, CONCURRENT_PLUGINS_SLIDER, METRIC_BADGE_HANDLERS, PLUGIN_ACTION_HANDLERS, PLUGIN_FILTER_ACTIVE, setElementDisabledState };

export type { DisableControlHost, PluginActionHost };
