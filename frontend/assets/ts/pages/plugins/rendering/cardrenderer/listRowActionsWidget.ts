/* SoAI - Plugins page list row actions widget [frontend/assets/ts/pages/plugins/rendering/cardrenderer/listRowActionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_UPDATE_ERROR } from '@core/state/pluginStatus.ts';
import { isObject } from '@core/typeGuards.ts';
import type { RoundButtonConfig } from '@core/ui/BaseCardRenderer.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@features/catalog/public.ts';
import { PLUGINS_ACTION_CLONE_PLUGIN, PLUGINS_ACTION_DELETE_PLUGIN, PLUGINS_ACTION_DISABLE_OVERRIDE, PLUGINS_ACTION_EDIT_CONFIG, PLUGINS_ACTION_ENABLE_OVERRIDE, PLUGINS_ACTION_INSTALL_BACKEND, PLUGINS_ACTION_MANAGE_BACKEND, PLUGINS_ACTION_STOP_PLUGIN } from '@features/plugins/public.ts';
import type { ActionState, PluginCardHost, PluginRecord } from '@pages/plugins/rendering/cardrenderer/types.ts';

const LOCAL_BACKEND_UNAVAILABLE_STATUSES: readonly string[] = [PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_BACKEND_UPDATING, PLUGIN_STATUS_INSTALL_ERROR, PLUGIN_STATUS_LOAD_ERROR, PLUGIN_STATUS_UPDATE_ERROR, PLUGIN_STATUS_BACKEND_UNINSTALL_ERROR, PLUGIN_STATUS_DELETE_ERROR, PLUGIN_STATUS_BACKEND_INSTALLING];

type PluginListActionConfig = RoundButtonConfig & { className: string };

const supportsBackendManagement = (plugin: PluginRecord): boolean => {
    const capabilities = isObject(plugin.capabilities) ? plugin.capabilities : {};
    return capabilities.supportsBackendInstallation !== false;
};

const appendPrimaryPluginActions = (buttons: PluginListActionConfig[], actionState: ActionState): void => {
    if (actionState.hasConfigAction) {
        buttons.push({ action: PLUGINS_ACTION_EDIT_CONFIG, className: 'ui-round-button ui-round-button--edit ui-round-button--edit-config', iconName: 'model-config', iconOptions: { strokeWidth: 1 }, label: i18n.t('plugins.actions.editConfig') });
    }
    if (actionState.hasCloneAction) {
        buttons.push({ action: PLUGINS_ACTION_CLONE_PLUGIN, className: 'ui-round-button ui-round-button--clone', iconName: 'copy', iconOptions: { strokeWidth: 1 }, label: i18n.t('plugins.actions.clonePlugin') });
    }
};

const appendOperationalPluginActions = (buttons: PluginListActionConfig[], plugin: PluginRecord, host: PluginCardHost): void => {
    const compatibility = host.compatibility.getPluginCompatibility(plugin);
    if (compatibility?.reason && compatibility.canOverride === true && !host.compatibility.isPluginPermanentlyDisabled(plugin)) {
        const isOverridden = compatibility.isOverridden === true;
        buttons.push({ action: isOverridden ? PLUGINS_ACTION_DISABLE_OVERRIDE : PLUGINS_ACTION_ENABLE_OVERRIDE, className: isOverridden ? 'ui-round-button ui-round-button--neutral' : 'ui-round-button ui-round-button--alert', iconName: isOverridden ? 'close' : 'warning', iconOptions: { strokeWidth: 1.5 }, label: isOverridden ? i18n.t('plugins.actions.disableOverride') : i18n.t('plugins.actions.overridePlugin') });
    }
};

const appendInstallPluginActions = (buttons: PluginListActionConfig[], plugin: PluginRecord, host: PluginCardHost): void => {
    if (host.compatibility.isPluginPermanentlyDisabled(plugin) || host.compatibility.requiresCompatibilityOverride(plugin)) {
        return;
    }
    const capabilities = isObject(plugin.capabilities) ? plugin.capabilities : {};
    const status = host.status.getPluginStatus(plugin);
    if ((status === PLUGIN_STATUS_BACKEND_NOT_INSTALLED || status === PLUGIN_STATUS_INSTALL_ERROR) && capabilities.supportsBackendInstallation !== false) {
        buttons.push({ action: PLUGINS_ACTION_INSTALL_BACKEND, className: 'ui-round-button ui-round-button--run-now', iconName: 'download', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.installBackend') });
        return;
    }
    if (LOCAL_BACKEND_UNAVAILABLE_STATUSES.includes(status)) {
        return;
    }
    const providerMode = resolveProviderMode(plugin);
    if (providerMode === PROVIDER_MODE.USER_MANAGED && (plugin.stats?.modelCount || 0) === 0) {
        buttons.push({ action: MODELS_ACTION_ADD_PROVIDER, className: 'ui-round-button ui-round-button--run-now', iconName: 'provider', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.addProvider') });
    } else if (capabilities.supportsModelDownload === true && (plugin.stats?.modelCount || 0) === 0) {
        buttons.push({ action: MODELS_ACTION_DOWNLOAD_MODEL, className: 'ui-round-button ui-round-button--run-now', iconName: 'download', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.downloadModel') });
    }
};

const appendBackendManagementAction = (buttons: PluginListActionConfig[], plugin: PluginRecord): void => {
    if (!supportsBackendManagement(plugin)) {
        return;
    }
    buttons.push({ action: PLUGINS_ACTION_MANAGE_BACKEND, className: 'ui-round-button ui-round-button--edit', iconName: 'backend-manage', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.manageBackend') });
};

const appendTerminalPluginActions = (buttons: PluginListActionConfig[], plugin: PluginRecord, host: PluginCardHost): void => {
    if (host.actions.isPluginStoppable(plugin)) {
        buttons.push({ action: PLUGINS_ACTION_STOP_PLUGIN, className: 'ui-round-button ui-round-button--stop', iconName: 'stop', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.stopPlugin') });
    }
    buttons.push({ action: PLUGINS_ACTION_DELETE_PLUGIN, className: 'ui-round-button ui-round-button--delete', iconName: 'close', iconOptions: { strokeWidth: 1.5 }, label: i18n.t('plugins.actions.deletePlugin') });
};

const buildPluginListActionConfigs = (plugin: PluginRecord, actionState: ActionState, host: PluginCardHost): readonly PluginListActionConfig[] => {
    const buttons: PluginListActionConfig[] = [];
    appendPrimaryPluginActions(buttons, actionState);
    appendOperationalPluginActions(buttons, plugin, host);
    appendInstallPluginActions(buttons, plugin, host);
    appendBackendManagementAction(buttons, plugin);
    appendTerminalPluginActions(buttons, plugin, host);
    return buttons;
};

export { buildPluginListActionConfigs };
