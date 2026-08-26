/* SoAI - Plugins feature download manager DOM contracts [frontend/assets/ts/features/plugins/modals/downloadmanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { updateTabAvailabilityState, updateTabSelectionState } from '@core/ui/controls/tabs/effects.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import type { RequiredClassNames } from '@core/ui/classNames.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { DownloadManagerHost, ManualPluginState } from '@features/plugins/modals/downloadmanager/contracts.ts';

const setDownloadModalBusyIfPresent = (host: DownloadManagerHost, modalId: string, isBusy: boolean, modalRoot: HTMLElement): void => {
    const confirmBtnCandidate = host.view.optionalHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    if (confirmBtnCandidate) {
        if (!(confirmBtnCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Plugin download modal confirm button must be a button');
        }
        const confirmBtn = confirmBtnCandidate;
        if (isBusy) {
            beginLoadingButton(confirmBtn);
        } else {
            clearLoadingButtonIfNeeded(confirmBtn);
        }
    }

    const urlInputCandidate = host.view.optionalHTMLElement(modalUiSelector(modalId, 'plugin-url'), modalRoot);
    if (urlInputCandidate) {
        if (!(urlInputCandidate instanceof HTMLInputElement)) {
            throw new TypeError('Plugin download modal URL input must be an input element');
        }
        const urlInput = urlInputCandidate;
        if (isBusy) {
            setBusyDisabledState(urlInput, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken });
        } else {
            const token = getBusyDisabledToken(urlInput);
            if (token) {
                setBusyDisabledState(urlInput, { isBusy: false, token });
            }
        }
    }

    const fileInputCandidate = host.view.optionalHTMLElement(modalUiSelector(modalId, 'plugin-file'), modalRoot);
    if (fileInputCandidate) {
        if (!(fileInputCandidate instanceof HTMLInputElement)) {
            throw new TypeError('Plugin download modal file input must be an input element');
        }
        const fileInput = fileInputCandidate;
        if (isBusy) {
            setBusyDisabledState(fileInput, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken });
        } else {
            const token = getBusyDisabledToken(fileInput);
            if (token) {
                setBusyDisabledState(fileInput, { isBusy: false, token });
            }
        }
    }

    const chooseFileBtnCandidate = host.view.optionalHTMLElement(modalUiSelector(modalId, 'choose-file-btn'), modalRoot);
    if (chooseFileBtnCandidate) {
        if (!(chooseFileBtnCandidate instanceof HTMLButtonElement)) {
            throw new TypeError('Plugin download modal choose file button must be a button');
        }
        const chooseFileBtn = chooseFileBtnCandidate;
        if (isBusy) {
            setBusyDisabledState(chooseFileBtn, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken, spinner: 'none' });
        } else {
            const token = getBusyDisabledToken(chooseFileBtn);
            if (token) {
                setBusyDisabledState(chooseFileBtn, { isBusy: false, token });
            }
        }
    }
};

const resetDownloadModalUi = (host: DownloadManagerHost, modalId: string, modalRoot: HTMLElement, options: { preserveActiveDownloads?: boolean } = {}): void => {
    const urlInput = host.view.optionalHTMLElement(modalUiSelector(modalId, 'plugin-url'), modalRoot);
    if (urlInput) {
        host.view.setUIValue(urlInput, '', { attribute: 'value' });
    }

    const fileInput = host.view.optionalHTMLElement(modalUiSelector(modalId, 'plugin-file'), modalRoot);
    if (fileInput) {
        host.view.setUIValue(fileInput, '', { attribute: 'value' });
    }

    syncSelectedPluginFileName(host, modalId, modalRoot, '');

    const operationProgressList = host.view.optionalHTMLElement(modalUiSelector(modalId, 'operation-progress-list'), modalRoot);
    if (operationProgressList && options.preserveActiveDownloads !== true) {
        operationProgressList.replaceChildren();
    }

    syncDownloadModalDisclaimerVisibility(host, modalId, modalRoot);
};

const syncSelectedPluginFileName = (host: DownloadManagerHost, modalId: string, modalRoot: HTMLElement, fileName: string): void => {
    const label = host.view.optionalHTMLElement(modalUiSelector(modalId, 'selected-file-name'), modalRoot);
    if (!label) {
        return;
    }
    const normalizedName = toTrimmedString(fileName);
    host.view.updateText(label, normalizedName);
    host.view.toggleClassName(label, 'u-hidden', !normalizedName);
};

const resolveConfirmButtonEnabled = (host: DownloadManagerHost, modalId: string, classNames: RequiredClassNames, modalRoot: HTMLElement): boolean => {
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const urlTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'url-tab'), modalRoot);
    const fileTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'file-tab'), modalRoot);
    const manualTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);

    const isUrlMode = urlTab.classList.contains(classNames.active);
    const isFileMode = fileTab.classList.contains(classNames.active);
    const isManualMode = manualTab.classList.contains(classNames.active);

    if (isUrlMode) {
        const urlValue = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'plugin-url'), 'Plugin download modal URL input', modalRoot).value);
        return Boolean(urlValue);
    }
    if (isFileMode) {
        return requireInputElement(resolver, modalUiSelector(modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot).files?.length ? true : false;
    }
    if (isManualMode) {
        return false;
    }
    return false;
};

const applyDownloadModalMode = (host: DownloadManagerHost, modalId: string, classNames: RequiredClassNames, mode: string, modalRoot: HTMLElement): { isManualMode: boolean } => {
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const isUrl = mode === 'url';
    const isFile = mode === 'file';
    const isManual = mode === 'manual';

    const urlTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'url-tab'), modalRoot);
    const fileTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'file-tab'), modalRoot);
    const manualTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);
    const confirmBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'confirm-download'), 'Plugin download modal confirm button', modalRoot);
    const urlForm = host.view.requireHTMLElement(modalUiSelector(modalId, 'url-form'), modalRoot);
    const fileForm = host.view.requireHTMLElement(modalUiSelector(modalId, 'file-form'), modalRoot);
    const manualForm = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-form'), modalRoot);
    const copyBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-copy-path'), 'Plugin download modal manual copy button', modalRoot);
    const openExplorerBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-open-file-explorer-btn'), 'Plugin download modal manual open file explorer button', modalRoot);
    const powerBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-power-btn'), 'Plugin download modal manual restart button', modalRoot);

    host.view.toggleClassName(urlTab, classNames.active, isUrl);
    host.view.toggleClassName(fileTab, classNames.active, isFile);
    host.view.toggleClassName(manualTab, classNames.active, isManual);
    host.view.toggleClassName(urlForm, classNames.hidden, !isUrl);
    host.view.toggleClassName(fileForm, classNames.hidden, !isFile);
    host.view.toggleClassName(manualForm, classNames.hidden, !isManual);
    host.view.toggleClassName(copyBtn, classNames.hidden, !isManual);
    host.view.toggleClassName(openExplorerBtn, classNames.hidden, !isManual);
    host.view.toggleClassName(powerBtn, classNames.hidden, !isManual);
    updateTabSelectionState(urlTab, urlForm, isUrl);
    updateTabSelectionState(fileTab, fileForm, isFile);
    updateTabSelectionState(manualTab, manualForm, isManual);
    for (const element of [manualForm, copyBtn, openExplorerBtn, powerBtn]) {
        host.view.updateAttribute(element, 'aria-hidden', isManual ? 'false' : 'true');
    }
    for (const element of [copyBtn, openExplorerBtn, powerBtn]) {
        host.view.updateProperty(element, 'tabIndex', isManual ? 0 : -1);
    }
    setControlDisabledState(openExplorerBtn, !isManual);
    setControlDisabledState(powerBtn, !isManual);
    if (!isManual) {
        setControlDisabledState(copyBtn, true);
    }

    if (isManual) {
        host.view.addClassName(confirmBtn, classNames.hidden);
    } else {
        host.view.removeClassName(confirmBtn, classNames.hidden);
        host.view.updateText(confirmBtn, isFile ? i18n.t('plugins.modal.addPlugin.confirmUpload') : i18n.t('plugins.modal.addPlugin.confirmDownload'));
    }

    syncDownloadModalDisclaimerVisibility(host, modalId, modalRoot);

    return { isManualMode: isManual };
};

const syncDownloadManualInstallVisibility = (host: DownloadManagerHost, modalId: string, classNames: RequiredClassNames, canUseManual: boolean, modalRoot: HTMLElement): void => {
    const manualTab = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-tab'), modalRoot);
    const manualForm = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-form'), modalRoot);
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const copyBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-copy-path'), 'Plugin download modal manual copy button', modalRoot);
    const openExplorerBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-open-file-explorer-btn'), 'Plugin download modal manual open file explorer button', modalRoot);
    const powerBtn = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-power-btn'), 'Plugin download modal manual restart button', modalRoot);

    host.view.toggleClassName(manualTab, classNames.hidden, !canUseManual);
    updateTabAvailabilityState(manualTab, canUseManual);
    if (canUseManual) {
        return;
    }
    const pathInput = requireInputElement(resolver, modalUiSelector(modalId, 'manual-plugins-path'), 'Plugin download modal manual plugins path input', modalRoot);
    const description = host.view.requireHTMLElement(modalUiSelector(modalId, 'manual-description'), modalRoot);
    host.view.updateProperty(pathInput, 'value', '');
    setTooltipText(pathInput, '');
    host.view.updateText(description, '');
    for (const element of [manualForm, copyBtn, openExplorerBtn, powerBtn]) {
        host.view.addClassName(element, classNames.hidden);
        host.view.updateAttribute(element, 'aria-hidden', 'true');
    }
    host.view.updateProperty(manualForm, 'hidden', true);
    for (const element of [copyBtn, openExplorerBtn, powerBtn]) {
        setControlDisabledState(element, true);
        host.view.updateProperty(element, 'tabIndex', -1);
    }
};

const syncDownloadModalDisclaimerVisibility = (host: DownloadManagerHost, modalId: string, modalRoot: HTMLElement): void => {
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const urlDisclaimer = host.view.optionalHTMLElement(modalUiSelector(modalId, 'url-disclaimer'), modalRoot);
    const fileDisclaimer = host.view.optionalHTMLElement(modalUiSelector(modalId, 'file-disclaimer'), modalRoot);
    const urlValue = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'plugin-url'), 'Plugin download modal URL input', modalRoot).value);
    const hasSelectedFile = requireInputElement(resolver, modalUiSelector(modalId, 'plugin-file'), 'Plugin download modal file input', modalRoot).files?.length ? true : false;

    if (urlDisclaimer) {
        host.view.toggleClassName(urlDisclaimer, 'u-hidden', !urlValue);
    }
    if (fileDisclaimer) {
        host.view.toggleClassName(fileDisclaimer, 'u-hidden', !hasSelectedFile);
    }
};

const updateManualPluginCopyControl = (host: DownloadManagerHost, modalId: string, pathValue: string, modalRoot: HTMLElement): void => {
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const button = requireButtonElement(resolver, modalUiSelector(modalId, 'manual-copy-path'), 'Plugin download modal manual copy button', modalRoot);
    const supported = host.session.hasClipboardSupport();
    const hasPath = Boolean(pathValue);

    setControlDisabledState(button, !(supported && hasPath));
    if (!supported) {
        setTooltipText(button, i18n.t('common.clipboard.copyUnavailable'));
        return;
    }
    if (!hasPath) {
        setTooltipText(button, i18n.t('plugins.modal.addPlugin.manualCopyUnavailable'));
        return;
    }
    setTooltipText(button, '');
};

const updateManualPluginPathField = (host: DownloadManagerHost, modalId: string, details: ManualPluginState | null, modalRoot: HTMLElement): void => {
    const resolver = createModalElementResolver(modalRoot, 'Plugin download modal');
    const input = requireInputElement(resolver, modalUiSelector(modalId, 'manual-plugins-path'), 'Plugin download modal manual plugins path input', modalRoot);
    const value = toTrimmedString(details?.resolvedPath);

    host.view.updateProperty(input, 'value', value);
    setTooltipText(input, value ? value : i18n.t('plugins.modal.addPlugin.manualPathPlaceholder'));
    updateManualPluginCopyControl(host, modalId, value, modalRoot);
};

export { applyDownloadModalMode, resetDownloadModalUi, resolveConfirmButtonEnabled, setDownloadModalBusyIfPresent, syncDownloadManualInstallVisibility, syncDownloadModalDisclaimerVisibility, syncSelectedPluginFileName, updateManualPluginCopyControl, updateManualPluginPathField };
