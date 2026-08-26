/* SoAI - Plugins page action dispatch [frontend/assets/ts/pages/plugins/controllers/pluginsPageActionDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { PLUGINS_ACTION_BACKEND_INSTALL_START, PLUGINS_ACTION_BACKEND_UNINSTALL, PLUGINS_ACTION_BACKEND_UPDATE_CHECK, PLUGINS_ACTION_CLONE_START, PLUGINS_ACTION_CONCURRENT_SAVE, PLUGINS_ACTION_CONCURRENT_SLIDER_INPUT, PLUGINS_ACTION_CONCURRENT_VALUE_INPUT, PLUGINS_ACTION_CONFIG_SAVE, PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE, PLUGINS_ACTION_DOWNLOAD_CONFIRM, PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE, PLUGINS_ACTION_DOWNLOAD_FILE_TAB, PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH, PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER, PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART, PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB, PLUGINS_ACTION_DOWNLOAD_PLUGIN, PLUGINS_ACTION_DOWNLOAD_URL_INPUT, PLUGINS_ACTION_DOWNLOAD_URL_TAB, PLUGINS_ACTION_INFO_COPY, PLUGINS_ACTION_OPEN_CONCURRENT, PLUGINS_ACTION_STOP_ALL } from '@features/plugins/public.ts';
import { PLUGINS_ACTION_SORT_LIST, PLUGINS_ACTION_TOGGLE_VIEW_MODE, type PluginsPageChangeActionId, type PluginsPageClickActionId, type PluginsPageInputActionId } from '@pages/plugins/actions.ts';

interface PluginsModalActions {
    openDownloadPluginModal(): void;
    handleStopAllPlugins(): Promise<void> | void;
    openConcurrentPluginsModal(): Promise<void> | void;
    handleDownloadChooseFileClick(): void;
    handleDownloadConfirm(): void;
    handleDownloadUrlTabClick(): void;
    handleDownloadFileTabClick(): void;
    handleDownloadManualTabClick(): void;
    handleDownloadManualCopyPath(): Promise<void> | void;
    handleDownloadManualOpenFileExplorer(): Promise<void> | void;
    handleDownloadManualRestart(): Promise<void> | void;
    handleConfigSave(): void;
    handleInfoCopy(): void;
}

interface PluginsBackendActions {
    handleBackendInstallStart(): void;
    handleBackendUpdateCheck(): Promise<void> | void;
    handleBackendUninstall(): Promise<void> | void;
    handleConcurrentSave(): Promise<void> | void;
    handleCloneStart(): Promise<void> | void;
    handleToggleViewMode(): void;
    handleSortList(): void;
}

interface PluginsFormActions {
    handleDownloadUrlInput(event: Event): void;
    handleConcurrentSliderInput(event: Event): void;
    handleConcurrentValueInput(event: Event): void;
    handleDownloadFileChange(event: Event): void;
}

interface PluginsPageActionDispatchHost {
    modal: PluginsModalActions;
    backend: PluginsBackendActions;
    form: PluginsFormActions;
}

type PluginsPageActionHandler = (host: PluginsPageActionDispatchHost, event: Event) => Promise<void> | void;

const CLICK_HANDLERS: Record<PluginsPageClickActionId, PluginsPageActionHandler> = {
    [PLUGINS_ACTION_DOWNLOAD_PLUGIN]: (host) => host.modal.openDownloadPluginModal(),
    [PLUGINS_ACTION_STOP_ALL]: (host) => host.modal.handleStopAllPlugins(),
    [PLUGINS_ACTION_OPEN_CONCURRENT]: (host) => host.modal.openConcurrentPluginsModal(),
    [PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE]: (host) => host.modal.handleDownloadChooseFileClick(),
    [PLUGINS_ACTION_DOWNLOAD_CONFIRM]: (host) => host.modal.handleDownloadConfirm(),
    [PLUGINS_ACTION_DOWNLOAD_URL_TAB]: (host) => host.modal.handleDownloadUrlTabClick(),
    [PLUGINS_ACTION_DOWNLOAD_FILE_TAB]: (host) => host.modal.handleDownloadFileTabClick(),
    [PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB]: (host) => host.modal.handleDownloadManualTabClick(),
    [PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH]: (host) => host.modal.handleDownloadManualCopyPath(),
    [PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER]: (host) => host.modal.handleDownloadManualOpenFileExplorer(),
    [PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART]: (host) => host.modal.handleDownloadManualRestart(),
    [PLUGINS_ACTION_CONFIG_SAVE]: (host) => host.modal.handleConfigSave(),
    [PLUGINS_ACTION_INFO_COPY]: (host) => host.modal.handleInfoCopy(),
    [PLUGINS_ACTION_BACKEND_INSTALL_START]: (host) => host.backend.handleBackendInstallStart(),
    [PLUGINS_ACTION_BACKEND_UPDATE_CHECK]: (host) => host.backend.handleBackendUpdateCheck(),
    [PLUGINS_ACTION_BACKEND_UNINSTALL]: (host) => host.backend.handleBackendUninstall(),
    [PLUGINS_ACTION_CONCURRENT_SAVE]: (host) => host.backend.handleConcurrentSave(),
    [PLUGINS_ACTION_CLONE_START]: (host) => host.backend.handleCloneStart(),
    [PLUGINS_ACTION_TOGGLE_VIEW_MODE]: (host) => host.backend.handleToggleViewMode(),
    [PLUGINS_ACTION_SORT_LIST]: (host) => host.backend.handleSortList()
};

const INPUT_HANDLERS: Record<PluginsPageInputActionId, PluginsPageActionHandler> = {
    [PLUGINS_ACTION_DOWNLOAD_URL_INPUT]: (host, event) => host.form.handleDownloadUrlInput(event),
    [PLUGINS_ACTION_CONCURRENT_SLIDER_INPUT]: (host, event) => host.form.handleConcurrentSliderInput(event),
    [PLUGINS_ACTION_CONCURRENT_VALUE_INPUT]: (host, event) => host.form.handleConcurrentValueInput(event)
};

const CHANGE_HANDLERS: Record<PluginsPageChangeActionId, PluginsPageActionHandler> = {
    [PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE]: (host, event) => host.form.handleDownloadFileChange(event)
};

const trackPluginsPageActionResult = (action: string, result: Promise<void> | void): void => {
    if (result === undefined) {
        return;
    }
    Promise.resolve(result).catch((error) => {
        errorHandler.error('PluginsPage', `Plugin page action failed: ${action}`, ensureError(error));
    });
};

const dispatchPluginsPageAction = (host: PluginsPageActionDispatchHost, event: Event, action: string): boolean => {
    const handlers: Partial<Record<string, PluginsPageActionHandler>> = event.type === 'click' ? CLICK_HANDLERS : event.type === 'input' ? INPUT_HANDLERS : CHANGE_HANDLERS;
    const handler = handlers[action];
    if (!handler) {
        return false;
    }
    const result = handler(host, event);
    trackPluginsPageActionResult(action, result);
    return true;
};

export { dispatchPluginsPageAction };
export type { PluginsPageActionDispatchHost };
