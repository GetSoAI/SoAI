/* SoAI - Hardware feature system info modal DOM contracts [frontend/assets/ts/features/hardware/modals/systeminfomodal/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocument } from '@core/environment/public.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { HARDWARE_SYSTEM_INFO_MODAL_ID } from '@features/hardware/modals/constants.ts';
import type { SystemInfoModalHost } from '@features/hardware/modals/systeminfomodal/types.ts';

const LOADING_SPINNER_CLASS = 'loading-spinner';
const LOADING_TEXT_CLASS = 'loading-text';

const REQUIRE_CLASS: {
    modalContent: string;
    copyButton: string;
    downloadButton: string;
    anonymizeToggle: string;
} = {
    modalContent: modalUiSelector(HARDWARE_SYSTEM_INFO_MODAL_ID, 'content'),
    copyButton: modalUiSelector(HARDWARE_SYSTEM_INFO_MODAL_ID, 'copy'),
    downloadButton: modalUiSelector(HARDWARE_SYSTEM_INFO_MODAL_ID, 'download'),
    anonymizeToggle: modalUiSelector(HARDWARE_SYSTEM_INFO_MODAL_ID, 'anonymize-toggle')
};

const requireContentElement = (host: SystemInfoModalHost, modalRoot: HTMLElement): HTMLElement => {
    return host.requireHTMLElement(REQUIRE_CLASS.modalContent, modalRoot);
};

const requireAnonymizeToggle = (host: SystemInfoModalHost, modalRoot: HTMLElement): HTMLInputElement => {
    return requireInputElement(host, REQUIRE_CLASS.anonymizeToggle, REQUIRE_CLASS.anonymizeToggle, modalRoot);
};

const copyAndDownloadButtons = (host: SystemInfoModalHost, modalRoot: HTMLElement): { copy: HTMLButtonElement; download: HTMLButtonElement } => ({
    copy: requireButtonElement(host, REQUIRE_CLASS.copyButton, REQUIRE_CLASS.copyButton, modalRoot),
    download: requireButtonElement(host, REQUIRE_CLASS.downloadButton, REQUIRE_CLASS.downloadButton, modalRoot)
});

const setCopyAndDownloadButtonsDisabled = (host: SystemInfoModalHost, buttons: { copy: HTMLButtonElement; download: HTMLButtonElement }, isDisabled: boolean): void => {
    const copyDisabled = isDisabled || !host.hasClipboardSupport();
    host.updateProperty(buttons.copy, 'disabled', copyDisabled);
    if (!isDisabled) {
        if (copyDisabled) {
            setTooltipText(buttons.copy, i18n.t('common.clipboard.copyUnavailable'));
        } else {
            setTooltipText(buttons.copy, '');
        }
    }
    host.updateProperty(buttons.download, 'disabled', isDisabled);
};

const renderLoadingState = (host: SystemInfoModalHost, modalRoot: HTMLElement): void => {
    const contentElement = requireContentElement(host, modalRoot);
    const documentRef = getDocument();
    const spinner = documentRef.createElement('span');
    const loadingText = documentRef.createElement('span');
    spinner.className = LOADING_SPINNER_CLASS;
    loadingText.className = LOADING_TEXT_CLASS;
    loadingText.textContent = i18n.t('hardware.modals.systemInfo.generating');

    host.addClassName(contentElement, 'is-loading');
    contentElement.textContent = '';
    host.setDataAttribute(contentElement, 'system-info', '');
    contentElement.appendChild(spinner);
    contentElement.appendChild(loadingText);
};

const clearLoadingState = (host: SystemInfoModalHost, contentElement: HTMLElement): void => {
    host.removeClassName(contentElement, 'is-loading');
};

export { clearLoadingState, copyAndDownloadButtons, requireAnonymizeToggle, requireContentElement, renderLoadingState, setCopyAndDownloadButtonsDisabled };
