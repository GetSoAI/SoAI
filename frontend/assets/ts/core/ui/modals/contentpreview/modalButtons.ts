/* SoAI - Shared UI modal buttons [frontend/assets/ts/core/ui/modals/contentpreview/modalButtons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { requireContentPreviewCopyButton, requireContentPreviewDownloadButton, requireContentPreviewEditButton, requireContentPreviewEnhanceButton, requireContentPreviewFooter, requireContentPreviewFooterCloseButton, requireContentPreviewHeaderCloseButton, requireContentPreviewHeaderColorContainer, requireContentPreviewOpenSourceButton, requireContentPreviewSaveButton, requireContentPreviewAttachButton } from '@core/ui/modals/contentpreview/dom.ts';
import type { ContentPreviewButtonLabels, ContentPreviewOpenRequest, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type ContentPreviewButtons = {
    footerClose: HTMLButtonElement;
    headerClose: HTMLButtonElement;
    download: HTMLButtonElement;
    copy: HTMLButtonElement;
    attach: HTMLButtonElement;
    openSource: HTMLButtonElement;
    edit: HTMLButtonElement;
    save: HTMLButtonElement;
    enhance: HTMLButtonElement;
    colorContainer: HTMLElement;
    footer: HTMLElement;
    header: HTMLElement;
};

const resolveContentPreviewButtons = (modalRoot: HTMLElement): ContentPreviewButtons => {
    const footer = requireContentPreviewFooter(modalRoot);
    const header = dom.resolve('.prompt-modal-header', modalRoot);
    if (!(header instanceof HTMLElement)) {
        throw new Error('Content preview modal header is missing');
    }
    return {
        footerClose: requireContentPreviewFooterCloseButton(modalRoot),
        headerClose: requireContentPreviewHeaderCloseButton(modalRoot),
        download: requireContentPreviewDownloadButton(modalRoot),
        copy: requireContentPreviewCopyButton(modalRoot),
        attach: requireContentPreviewAttachButton(modalRoot),
        openSource: requireContentPreviewOpenSourceButton(modalRoot),
        edit: requireContentPreviewEditButton(modalRoot),
        save: requireContentPreviewSaveButton(modalRoot),
        enhance: requireContentPreviewEnhanceButton(modalRoot),
        colorContainer: requireContentPreviewHeaderColorContainer(modalRoot),
        footer,
        header
    };
};

const setButtonVisible = (button: HTMLButtonElement, visible: boolean): void => {
    button.classList.toggle('u-hidden', !visible);
    button.setAttribute('aria-hidden', visible ? 'false' : 'true');
};

const setButtonText = (button: HTMLButtonElement, label: string): void => {
    button.textContent = label;
    button.setAttribute('aria-label', label);
};

const setButtonTitle = (button: HTMLButtonElement, title: string): void => {
    setTooltipText(button, title);
};

const setIconButtonLabel = (button: HTMLButtonElement, label: string): void => {
    button.setAttribute('aria-label', label);
    setButtonTitle(button, label);
};

const applyButtonLabels = (modalRoot: HTMLElement, labels: ContentPreviewButtonLabels): void => {
    const buttons = resolveContentPreviewButtons(modalRoot);
    setButtonText(buttons.footerClose, labels.close);
    setButtonTitle(buttons.footerClose, labels.close);
    setIconButtonLabel(buttons.headerClose, labels.close);
    setButtonText(buttons.download, labels.download);
    setButtonTitle(buttons.download, labels.download);
    setButtonText(buttons.copy, labels.copy);
    setButtonTitle(buttons.copy, labels.copy);
    setButtonText(buttons.attach, labels.attach);
    setButtonTitle(buttons.attach, labels.attach);
    setButtonText(buttons.openSource, labels.openSource);
    setButtonTitle(buttons.openSource, labels.openSource);
    setButtonText(buttons.edit, labels.edit);
    setButtonTitle(buttons.edit, labels.edit);
    setButtonText(buttons.save, labels.save);
    setButtonTitle(buttons.save, labels.save);
    setButtonText(buttons.enhance, labels.enhance);
    setButtonTitle(buttons.enhance, labels.enhance);
};

const applyEditingUiState = (modalRoot: HTMLElement, request: ContentPreviewOpenRequest | null, nextEditing: boolean): void => {
    const buttons = resolveContentPreviewButtons(modalRoot);
    const textRequest = request?.type === 'text' ? request : null;
    const hasText = Boolean(textRequest?.baseline.content && textRequest.baseline.content.trim().length > 0);
    const hideEmptyTextActions = textRequest?.hideActionsWhenEmpty === true && !hasText;
    modalRoot.classList.toggle('is-editing', nextEditing);
    buttons.footer.classList.toggle('is-editing', nextEditing);
    buttons.header.classList.toggle('is-editing', nextEditing);

    if (request) {
        const closeLabel = nextEditing && request.type === 'text' ? request.labels.cancel : request.labels.close;
        setButtonText(buttons.footerClose, closeLabel);
        setButtonTitle(buttons.footerClose, closeLabel);
        setIconButtonLabel(buttons.headerClose, closeLabel);
    }

    const hasColorToolkit = request?.type === 'text' && request.colorToolkit != null;
    const colorVisible = Boolean(hasColorToolkit && nextEditing);
    buttons.colorContainer.classList.toggle('u-hidden', !colorVisible);
    buttons.colorContainer.setAttribute('aria-hidden', colorVisible ? 'false' : 'true');
    setButtonVisible(buttons.edit, Boolean(!nextEditing && request?.type === 'text' && request.editable));
    setButtonVisible(buttons.save, Boolean(nextEditing && request?.type === 'text' && request.editable));
    setButtonVisible(buttons.enhance, Boolean(!nextEditing && textRequest?.enhance && !hideEmptyTextActions));
    setButtonVisible(buttons.download, Boolean(!nextEditing && request?.onRequestDownload && !hideEmptyTextActions));
    setButtonVisible(buttons.copy, Boolean(!nextEditing && textRequest?.onRequestCopy && !hideEmptyTextActions));
    setButtonVisible(buttons.attach, Boolean(!nextEditing && request?.onRequestAttach));
    setButtonVisible(buttons.openSource, Boolean(!nextEditing && request?.openSourceUrl));
};

const applyTextEmptyDisableState = (modalRoot: HTMLElement, request: ContentPreviewTextRequest): void => {
    const buttons = resolveContentPreviewButtons(modalRoot);
    const hasText = Boolean(request.baseline.content && request.baseline.content.trim().length > 0);
    const disableCopy = request.disableCopyWhenEmpty && !hasText;
    const disableDownload = request.disableDownloadWhenEmpty && !hasText;
    buttons.copy.disabled = disableCopy;
    setButtonTitle(buttons.copy, disableCopy ? request.labels.emptyCopyTitle : request.labels.copy);
    buttons.download.disabled = disableDownload;
    setButtonTitle(buttons.download, disableDownload ? request.labels.emptyDownloadTitle : request.labels.download);
    const enhanceConfig = request.enhance;
    if (enhanceConfig) {
        const enabled = enhanceConfig.isEnabledForBaseline(request.baseline);
        buttons.enhance.disabled = !enabled;
        if (!enabled && enhanceConfig.disabledTitle) {
            setButtonTitle(buttons.enhance, enhanceConfig.disabledTitle);
        }
    } else {
        buttons.enhance.disabled = false;
    }
};

const applyBusyState = (modalRoot: HTMLElement, busy: boolean): void => {
    const buttons = resolveContentPreviewButtons(modalRoot);

    if (busy) {
        setBusyDisabledState(buttons.footerClose, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken, spinner: 'none' });
        setBusyDisabledState(buttons.headerClose, { isBusy: true, reuseExistingToken: true, createToken: createBusyDisabledToken, spinner: 'none' });
        beginLoadingButton(buttons.save);
        return;
    }

    const footerCloseToken = getBusyDisabledToken(buttons.footerClose);
    if (footerCloseToken) {
        setBusyDisabledState(buttons.footerClose, { isBusy: false, token: footerCloseToken });
    }
    const headerCloseToken = getBusyDisabledToken(buttons.headerClose);
    if (headerCloseToken) {
        setBusyDisabledState(buttons.headerClose, { isBusy: false, token: headerCloseToken });
    }
    clearLoadingButtonIfNeeded(buttons.save);
};

export { applyBusyState, applyButtonLabels, applyEditingUiState, applyTextEmptyDisableState };
