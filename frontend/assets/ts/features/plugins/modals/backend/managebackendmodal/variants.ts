/* SoAI - Manage backend modal variant loading [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/variants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderManageBackendInfoStatus } from '@features/plugins/modals/backend/managebackendmodal/backendInfo.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { loadBackendVariantSelector } from '@features/plugins/modals/backend/backendVariantSelector.ts';
import { hasResolvedBackendInstallation } from '@features/plugins/modals/backend/backendVariantOptions.ts';
import type { BackendManagerDependencies, ManageState } from '@features/plugins/modals/backend/managebackendmodal/types.ts';
import { renderManageBackendVariantInfo, resetManageBackendButtons, setManageBackendButtonsDisabled, syncManageBackendFooterActions } from '@features/plugins/modals/backend/managebackendmodal/view.ts';

interface ManageBackendVariantLoadDependencies extends BackendManagerDependencies {
    state: ManageState;
    signal: AbortSignal;
    variantLoadToken: SequenceToken;
    invalidateComparison(): void;
    flushCatalogRefresh(): void;
}

const renderVariantResolution = (dependencies: ManageBackendVariantLoadDependencies, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord, loaded: boolean): void => {
    dependencies.state.backendVariantsReady = loaded;
    dependencies.host.view.toggleClassName(dependencies.host.view.requireHTMLElement(modalUiSelector(modalId, 'retry-variants'), modalRoot), dependencies.classNames.hidden, loaded);
    renderManageBackendInfoStatus(dependencies.host.view, dependencies.host.status, dependencies.state.currentPlugin ?? plugin, modalRoot, dependencies.host.status.getStatusManager(), loaded ? 'ready' : 'load-error', dependencies.host.catalog.isFresh());
};

const loadManageBackendVariants = async (dependencies: ManageBackendVariantLoadDependencies, modalId: string, modalRoot: HTMLElement, plugin: PluginRecord, token: number): Promise<void> => {
    dependencies.state.backendVariantsLoading = true;
    const payload = await loadBackendVariantSelector({ host: dependencies.host, security: dependencies.security }, modalId, modalRoot, String(plugin.name), {
        disabled: false,
        signal: dependencies.signal,
        onSelectionSettled: dependencies.flushCatalogRefresh,
        onSavingChange: (saving, installationResolved): void => {
            dependencies.state.backendVariantSaving = saving;
            dependencies.state.backendVariantsReady = !saving && installationResolved;
            if (saving) {
                dependencies.invalidateComparison();
                dependencies.state.updateInfo = null;
                dependencies.host.status.setCurrentUpdateInfo(null);
                resetManageBackendButtons(dependencies, modalId, modalRoot);
            } else {
                renderVariantResolution(dependencies, modalId, modalRoot, plugin, installationResolved);
            }
            const actionable = syncManageBackendFooterActions(dependencies, modalId, modalRoot, dependencies.state.currentPlugin);
            setManageBackendButtonsDisabled(dependencies, modalId, modalRoot, !dependencies.state.backendVariantsReady || dependencies.state.operationActive || !actionable || !dependencies.host.catalog.isFresh());
        },
        isCurrent: (): boolean => dependencies.variantLoadToken.isActive(token) && dependencies.state.currentPlugin?.name === plugin.name
    });
    if (!dependencies.variantLoadToken.isActive(token) || dependencies.state.currentPlugin?.name !== plugin.name) {
        return;
    }
    dependencies.state.backendVariantsLoading = false;
    const loaded = payload !== null && hasResolvedBackendInstallation(payload);
    if (payload) {
        renderManageBackendVariantInfo(dependencies.host.view, modalId, modalRoot, payload);
    }
    dependencies.state.backendVariantsReady = loaded;
    if (dependencies.state.operationActive) {
        setManageBackendButtonsDisabled({ host: dependencies.host, classNames: dependencies.classNames }, modalId, modalRoot, true);
        return;
    }
    renderVariantResolution(dependencies, modalId, modalRoot, plugin, loaded);
    const footerDependencies = { host: dependencies.host, classNames: dependencies.classNames };
    const hasBackendAction = syncManageBackendFooterActions(footerDependencies, modalId, modalRoot, dependencies.state.currentPlugin);
    setManageBackendButtonsDisabled(footerDependencies, modalId, modalRoot, !loaded || !hasBackendAction || !dependencies.host.catalog.isFresh() || !dependencies.host.catalog.getPlugin(String(plugin.name)));
    dependencies.flushCatalogRefresh();
};

export { loadManageBackendVariants };
