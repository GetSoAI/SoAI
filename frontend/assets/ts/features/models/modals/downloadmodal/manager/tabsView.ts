/* SoAI - Models feature tabs view [frontend/assets/ts/features/models/modals/downloadmodal/manager/tabsView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { updateTabAvailabilityState, updateTabSelectionState } from '@core/ui/controls/tabs/effects.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { getManualDiscoveryState, resetManualDiscoveryState } from '@features/models/modals/downloadmodal/manager/state.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';

const updateVariantControlsVisibility = (runtime: DownloadModalManagerRuntime): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const manualTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);
    const hideVariantControls = runtime.host.session.dom.hasClass(manualTab, CSS_CLASSES.ACTIVE);
    const variantButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'model-variant-check'), modalRoot);
    runtime.host.view.toggleClassName(variantButton, CSS_CLASSES.HIDDEN, hideVariantControls);
    if (hideVariantControls) {
        runtime.host.execution.variantProbe.reset();
        runtime.host.view.updateProperty(variantButton, 'disabled', true);
        return;
    }
    runtime.host.execution.variantProbe.updateButtonState();
};

const requireModalButton = (runtime: DownloadModalManagerRuntime, modalId: string, token: string, modalRoot: Element, errorContext: string): HTMLButtonElement => {
    const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
    if (!(element instanceof HTMLButtonElement)) {
        throw new TypeError(errorContext);
    }
    return element;
};

const renderConfirmButtonContent = (runtime: DownloadModalManagerRuntime, label: string): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    runtime.host.view.updateText(confirmButton, label);
    runtime.host.view.updateAttribute(confirmButton, 'aria-label', label);
    setTooltipText(confirmButton, label);
};

const updateDownloadModalUI = (runtime: DownloadModalManagerRuntime, activeTab: string): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const canUseManual = runtime.host.session.isAdmin();
    const resolvedActiveTab = canUseManual || activeTab !== 'manual' ? activeTab : 'download';
    const isDownload = resolvedActiveTab === 'download';
    const isManual = resolvedActiveTab === 'manual';
    const isProvider = resolvedActiveTab === 'provider';
    const setHidden = (token: string, hidden: boolean): void => {
        const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.toggleClassName(element, CSS_CLASSES.HIDDEN, hidden);
    };
    const setActive = (token: string, active: boolean): void => {
        const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.toggleClassName(element, CSS_CLASSES.ACTIVE, active);
    };
    setActive('download-tab', isDownload);
    setActive('provider-tab', isProvider);
    setActive('manual-tab', isManual);
    setHidden('manual-tab', !canUseManual);
    setHidden('download-form', !isDownload);
    setHidden('provider-form', !isProvider);
    setHidden('manual-add-panel', !isManual);
    const downloadTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-tab'), modalRoot);
    const providerTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-tab'), modalRoot);
    const manualTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);
    const downloadPanel = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'download-form'), modalRoot);
    const providerPanel = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-form'), modalRoot);
    const manualPanel = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-add-panel'), modalRoot);
    updateTabSelectionState(downloadTab, downloadPanel, isDownload);
    updateTabSelectionState(providerTab, providerPanel, isProvider);
    updateTabSelectionState(manualTab, manualPanel, isManual);
    setHidden('manual-discovery-button', !isManual);
    setHidden('manual-copy-path', !isManual);
    setHidden('manual-open-file-explorer', !isManual);
    if (!canUseManual) {
        const manualState = getManualDiscoveryState(runtime);
        resetManualDiscoveryState(manualState);
        const pathInput = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-models-path'), modalRoot);
        runtime.host.view.updateText(runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-discovery-text'), modalRoot), '');
        runtime.host.view.setUIValue(pathInput, '', { attribute: 'value' });
        setTooltipText(pathInput, '');
    }
    for (const token of ['manual-tab']) {
        const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.updateAttribute(element, 'aria-hidden', canUseManual ? 'false' : 'true');
        runtime.host.view.updateProperty(element, 'tabIndex', canUseManual ? 0 : -1);
    }
    for (const token of ['manual-add-panel', 'manual-discovery-button', 'manual-copy-path', 'manual-open-file-explorer']) {
        const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.updateAttribute(element, 'aria-hidden', isManual ? 'false' : 'true');
    }
    for (const token of ['manual-discovery-button', 'manual-copy-path', 'manual-open-file-explorer']) {
        const element = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, token), modalRoot);
        runtime.host.view.updateProperty(element, 'tabIndex', isManual ? 0 : -1);
    }
    const manualDiscoveryButton = requireModalButton(runtime, modalId, 'manual-discovery-button', modalRoot, 'Download modal manual discovery button must be a button');
    const manualOpenFileExplorerButton = requireModalButton(runtime, modalId, 'manual-open-file-explorer', modalRoot, 'Download modal manual open file explorer button must be a button');
    const manualCopyButton = requireModalButton(runtime, modalId, 'manual-copy-path', modalRoot, 'Download modal manual copy button must be a button');
    setControlDisabledState(manualDiscoveryButton, !isManual);
    setControlDisabledState(manualOpenFileExplorerButton, !isManual);
    if (!isManual) {
        setControlDisabledState(manualCopyButton, true);
    }
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    if (isManual) {
        runtime.host.view.addClassName(confirmButton, CSS_CLASSES.HIDDEN);
        updateVariantControlsVisibility(runtime);
        return;
    }
    runtime.host.view.removeClassName(confirmButton, CSS_CLASSES.HIDDEN);
    if (isDownload) {
        renderConfirmButtonContent(runtime, i18n.t('models.modal.addModel.confirmDownload'));
    } else {
        renderConfirmButtonContent(runtime, i18n.t('models.modal.addProvider.confirmProvider'));
    }
    updateVariantControlsVisibility(runtime);
};

const updateModalTabsVisibility = (runtime: DownloadModalManagerRuntime, autoSwitchTab = false): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const hasProviders = runtime.host.catalog.getProviderPlugins().length > 0;
    const providerTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-tab'), modalRoot);
    const providerForm = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-form'), modalRoot);
    const manualTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);
    const canUseManual = runtime.host.session.isAdmin();
    runtime.host.view.toggleClassName(providerTab, CSS_CLASSES.HIDDEN, !hasProviders);
    runtime.host.view.toggleClassName(providerForm, CSS_CLASSES.HIDDEN, !hasProviders);
    runtime.host.view.toggleClassName(manualTab, CSS_CLASSES.HIDDEN, !canUseManual);
    updateTabAvailabilityState(providerTab, hasProviders);
    updateTabAvailabilityState(manualTab, canUseManual);
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    if (!runtime.host.session.dom.hasClass(manualTab, CSS_CLASSES.ACTIVE)) {
        runtime.host.view.removeClassName(confirmButton, CSS_CLASSES.HIDDEN);
    }
    if (!canUseManual && runtime.host.session.dom.hasClass(manualTab, CSS_CLASSES.ACTIVE)) {
        updateDownloadModalUI(runtime, 'download');
        return;
    }
    if (!hasProviders && runtime.host.session.dom.hasClass(providerTab, CSS_CLASSES.ACTIVE)) {
        updateDownloadModalUI(runtime, 'download');
        return;
    }
    if (hasProviders && autoSwitchTab) {
        updateDownloadModalUI(runtime, 'provider');
    }
};

export { updateDownloadModalUI, updateModalTabsVisibility, updateVariantControlsVisibility };
