/* SoAI - Plugins feature public surface [frontend/assets/ts/features/plugins/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { PAGE_ID } from '@features/plugins/contracts/PluginsPageSupport.ts';
export {
    PLUGINS_ACTION_BACKEND_INSTALL_START,
    PLUGINS_ACTION_BACKEND_UNINSTALL,
    PLUGINS_ACTION_BACKEND_UPDATE_CHECK,
    PLUGINS_ACTION_CLONE_PLUGIN,
    PLUGINS_ACTION_CLONE_START,
    PLUGINS_ACTION_CONCURRENT_SAVE,
    PLUGINS_ACTION_CONCURRENT_SLIDER_INPUT,
    PLUGINS_ACTION_CONCURRENT_VALUE_INPUT,
    PLUGINS_ACTION_CONFIG_SAVE,
    PLUGINS_ACTION_DELETE_PLUGIN,
    PLUGINS_ACTION_DISABLE_OVERRIDE,
    PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE,
    PLUGINS_ACTION_DOWNLOAD_CONFIRM,
    PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE,
    PLUGINS_ACTION_DOWNLOAD_FILE_TAB,
    PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH,
    PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER,
    PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART,
    PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB,
    PLUGINS_ACTION_DOWNLOAD_PLUGIN,
    PLUGINS_ACTION_DOWNLOAD_URL_INPUT,
    PLUGINS_ACTION_DOWNLOAD_URL_TAB,
    PLUGINS_ACTION_EDIT_CONFIG,
    PLUGINS_ACTION_ENABLE_OVERRIDE,
    PLUGINS_ACTION_INFO_COPY,
    PLUGINS_ACTION_INSTALL_BACKEND,
    PLUGINS_ACTION_MANAGE_BACKEND,
    PLUGINS_ACTION_METRIC_BADGE,
    PLUGINS_ACTION_OPEN_CONCURRENT,
    PLUGINS_ACTION_OPEN_PLUGIN,
    PLUGINS_ACTION_STOP_ALL,
    PLUGINS_ACTION_STOP_PLUGIN,
    PLUGINS_ACTION_TOGGLE_ENABLED
} from '@features/plugins/contracts/pluginActionIds.ts';
export { C_CLICK, C_DISABLED, C_HIDDEN, CONCURRENT_PLUGINS_SLIDER, METRIC_BADGE_HANDLERS, PLUGIN_ACTION_HANDLERS, PLUGIN_FILTER_ACTIVE, setElementDisabledState } from '@features/plugins/contracts/pluginPageSupport.ts';
export type { DisableControlHost, PluginActionHost } from '@features/plugins/contracts/pluginPageSupport.ts';
export type { PluginsFiltersStorage } from '@features/plugins/contracts/pluginPageStorage.ts';
export { startPluginsModalLedUpdates, stopPluginsModalLedUpdates } from '@features/plugins/modals/pluginsModalLedUpdates.ts';
export type { PluginsModalLedUpdateHost } from '@features/plugins/modals/pluginsModalLedUpdates.ts';
export { DOWNLOAD_PLUGIN_MODAL_ID } from '@features/plugins/modals/downloadPluginModal.ts';
export { PLUGIN_CONFIG_MODAL_ID } from '@features/plugins/modals/pluginConfigModal.ts';
export { PLUGIN_INFO_MODAL_ID } from '@features/plugins/modals/pluginInfoModal.ts';
export { PLUGINS_INTRO_MODAL_ID } from '@features/plugins/modals/pluginsIntroModal.ts';
export { CLONE_PLUGIN_MODAL_ID } from '@features/plugins/modals/clonePluginModal.ts';
export { CONCURRENT_PLUGINS_MODAL_ID } from '@features/plugins/modals/concurrentPluginsModal.ts';
export { MANAGE_BACKEND_MODAL_ID } from '@features/plugins/modals/backendModals.ts';
export { normalizeBackendVariantOptions } from '@features/plugins/modals/backend/backendVariantOptions.ts';
export type { BackendVariantOption } from '@features/plugins/modals/backend/backendVariantOptions.ts';
export type { BackendTaskActionOptions, BackendTaskCommandOptions } from '@features/plugins/modals/backend/backendTypes.ts';
export { PLUGINS_INTRO_FIRST_RUN_REGISTRATION } from '@features/plugins/firstRunRegistration.ts';
export { createPluginsManagerHostCallbacks } from '@features/plugins/modals/modalCallbacks.ts';
export type { PluginsManagerHostCallbacks, PluginsManagerHostCallbacksDependencies } from '@features/plugins/modals/modalCallbacks.ts';
export { createPluginsModalManagers } from '@features/plugins/modals/modalManagers.ts';
export type { PluginsModalManagers, PluginsModalManagersDependencies } from '@features/plugins/modals/modalManagerContracts.ts';
export { PluginDownloadModalManager } from '@features/plugins/modals/downloadmanager/service.ts';
export type { DownloadManagerHost } from '@features/plugins/modals/downloadmanager/service.ts';
export type { ProgressReporter } from '@features/plugins/modals/downloadmanager/contracts.ts';
export { ConfigManager } from '@features/plugins/modals/ConfigManager.ts';
export type { ConfigurationManager } from '@features/plugins/modals/config/types.ts';
export { InfoManager } from '@features/plugins/modals/InfoManager.ts';
export { ConcurrentModalManager } from '@features/plugins/modals/ConcurrentModalManager.ts';
export { ManageBackendModalManager } from '@features/plugins/modals/backend/managebackendmodal/service.ts';
export { CloneModalManager } from '@features/plugins/modals/CloneModalManager.ts';
