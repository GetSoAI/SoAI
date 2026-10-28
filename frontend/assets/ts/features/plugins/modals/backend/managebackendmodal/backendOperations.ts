/* SoAI - Managed backend operation execution [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/backendOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderManageBackendInfoStatus } from '@features/plugins/modals/backend/managebackendmodal/backendInfo.ts';
import type { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { i18n } from '@core/i18n/index.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { requireBackendVariantSelectorValue } from '@features/plugins/modals/backend/backendVariantSelector.ts';
import { runBackendOperation } from '@features/plugins/modals/backend/backendOperationRunner.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { hideManageBackendUpdateControls, setManageBackendButtonsDisabled, syncManageBackendFooterActions } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

interface ManageBackendOperationDependencies extends BackendManagerDependencies {
    modalId: string;
    operationToken: SequenceToken;
    state: ManageState;
    refreshAfterOperation(plugin: PluginRecord): void;
    flushCatalogRefresh(): void;
}

const isCurrentOperation = (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord, operationToken: number): boolean => {
    return dependencies.operationToken.isActive(operationToken) && dependencies.state.currentPlugin?.name === plugin.name;
};

const setButtonsIfCurrent = (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord, operationToken: number, modalRoot: HTMLElement, disabled: boolean): void => {
    if (isCurrentOperation(dependencies, plugin, operationToken)) {
        dependencies.state.operationActive = false;
        setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, disabled);
        dependencies.flushCatalogRefresh();
    }
};

const restoreBadgeIfCurrent = (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord, operationToken: number, modalRoot: HTMLElement): void => {
    if (isCurrentOperation(dependencies, plugin, operationToken)) {
        const current = dependencies.host.catalog.getPlugin(String(plugin.name));
        renderManageBackendInfoStatus(dependencies.host.view, dependencies.host.status, current ?? plugin, modalRoot, dependencies.host.status.getStatusManager(), 'ready', dependencies.host.catalog.isFresh() && current !== null);
    }
};

const refreshIfCurrent = (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord, operationToken: number): void => {
    if (isCurrentOperation(dependencies, plugin, operationToken) && dependencies.state.backendVariantsReady) {
        dependencies.refreshAfterOperation(plugin);
    }
};

const startManageBackendUpdate = async (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord): Promise<void> => {
    if (dependencies.state.operationActive) return;
    const pluginLabel = dependencies.host.operations.formatPluginName(String(plugin.name)) || String(plugin.name);
    const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
    const backendVariantId = requireBackendVariantSelectorValue(dependencies.host, dependencies.modalId, modalRoot);
    const operationToken = dependencies.operationToken.next();
    dependencies.state.operationActive = true;
    await runBackendOperation(dependencies.host.operations, plugin, {
        commandType: WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_UPDATE,
        backendVariantId: backendVariantId,
        operationMeta: { type: 'backend-update' },
        loadingMessage: i18n.t('plugins.loading.updatingBackend'),
        okMessage: i18n.t('plugins.notifications.backendUpdateSuccess', { plugin: pluginLabel }),
        failMessage: i18n.t('plugins.notifications.backendUpdateFailed'),
        onBefore: (): void => {
            setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, true);
            renderManageBackendInfoStatus(dependencies.host.view, dependencies.host.status, plugin, modalRoot, dependencies.host.status.getStatusManager(), 'updating', dependencies.host.catalog.isFresh());
        },
        onAfter: (): void => {
            restoreBadgeIfCurrent(dependencies, plugin, operationToken, modalRoot);
            setButtonsIfCurrent(dependencies, plugin, operationToken, modalRoot, !dependencies.state.backendVariantsReady);
        },
        onSuccess: (): void => refreshIfCurrent(dependencies, plugin, operationToken),
        onFailure: (): void => refreshIfCurrent(dependencies, plugin, operationToken)
    });
};

const startManageBackendInstall = async (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord): Promise<void> => {
    if (dependencies.state.operationActive) return;
    const pluginLabel = dependencies.host.operations.formatPluginName(String(plugin.name)) || String(plugin.name);
    const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
    const backendVariantId = requireBackendVariantSelectorValue(dependencies.host, dependencies.modalId, modalRoot);
    const operationToken = dependencies.operationToken.next();
    dependencies.state.operationActive = true;
    await runBackendOperation(dependencies.host.operations, plugin, {
        commandType: WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_INSTALL,
        backendVariantId: backendVariantId,
        operationMeta: { type: 'backend-install' },
        loadingMessage: i18n.t('plugins.loading.installingBackend'),
        okMessage: i18n.t('plugins.notifications.backendInstallSuccess', { plugin: pluginLabel }),
        failMessage: i18n.t('plugins.notifications.backendInstallFailed'),
        onBefore: (): void => {
            setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, true);
            renderManageBackendInfoStatus(dependencies.host.view, dependencies.host.status, plugin, modalRoot, dependencies.host.status.getStatusManager(), 'installing', dependencies.host.catalog.isFresh());
        },
        onAfter: (): void => {
            restoreBadgeIfCurrent(dependencies, plugin, operationToken, modalRoot);
            setButtonsIfCurrent(dependencies, plugin, operationToken, modalRoot, !dependencies.state.backendVariantsReady);
        },
        onSuccess: (): void => refreshIfCurrent(dependencies, plugin, operationToken),
        onFailure: (): void => refreshIfCurrent(dependencies, plugin, operationToken)
    });
};

const startManageBackendUninstall = async (dependencies: ManageBackendOperationDependencies, plugin: PluginRecord): Promise<void> => {
    if (dependencies.state.operationActive) return;
    const pluginLabel = dependencies.host.operations.formatPluginName(String(plugin.name)) || String(plugin.name);
    const operationToken = dependencies.operationToken.next();
    dependencies.state.operationActive = true;
    await runBackendOperation(dependencies.host.operations, plugin, {
        commandType: WEBSOCKET_MESSAGE_TYPES.PLUGIN_BACKEND_REMOVE,
        deleteModels: false,
        operationMeta: { type: 'backend-remove' },
        loadingMessage: i18n.t('plugins.loading.uninstallingBackend'),
        okMessage: i18n.t('plugins.notifications.backendUninstallSuccess', { plugin: pluginLabel }),
        failMessage: i18n.t('plugins.notifications.backendUninstallFailed'),
        onBefore: (): void => {
            const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
            setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, true);
            hideManageBackendUpdateControls({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot);
            renderManageBackendInfoStatus(dependencies.host.view, dependencies.host.status, plugin, modalRoot, dependencies.host.status.getStatusManager(), 'uninstalling', dependencies.host.catalog.isFresh());
        },
        onAfter: (): void => {
            if (isCurrentOperation(dependencies, plugin, operationToken)) {
                dependencies.state.operationActive = false;
                const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
                syncManageBackendFooterActions({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, plugin);
                setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, dependencies.modalId, modalRoot, !dependencies.state.backendVariantsReady);
                restoreBadgeIfCurrent(dependencies, plugin, operationToken, modalRoot);
                dependencies.flushCatalogRefresh();
            }
        },
        onSuccess: (): void => refreshIfCurrent(dependencies, plugin, operationToken),
        onFailure: (): void => refreshIfCurrent(dependencies, plugin, operationToken)
    });
};

export { startManageBackendInstall, startManageBackendUninstall, startManageBackendUpdate };
export type { ManageBackendOperationDependencies };
