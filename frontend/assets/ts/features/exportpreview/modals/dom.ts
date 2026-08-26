/* SoAI - Shared export preview modal DOM helpers [frontend/assets/ts/features/exportpreview/modals/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement } from '@core/dom/typedElements.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { EXPORT_PREVIEW_MODAL_ID } from '@features/exportpreview/modals/constants.ts';
import type { ExportPreviewModalHost } from '@features/exportpreview/modals/types.ts';

const SELECTORS: {
    title: string;
    content: string;
    download: string;
    loading: string;
} = {
    title: modalUiSelector(EXPORT_PREVIEW_MODAL_ID, 'title'),
    content: modalUiSelector(EXPORT_PREVIEW_MODAL_ID, 'content'),
    download: modalUiSelector(EXPORT_PREVIEW_MODAL_ID, 'download'),
    loading: '.content-loading'
};

const requireTitleElement = (host: ExportPreviewModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.title, modalRoot);

const requireContentElement = (host: ExportPreviewModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.content, modalRoot);

const requireLoadingOverlay = (host: ExportPreviewModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.loading, modalRoot);

const requireDownloadButton = (host: ExportPreviewModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.download, SELECTORS.download, modalRoot);
};

const setLoadingVisible = (host: ExportPreviewModalHost, modalRoot: HTMLElement, visible: boolean): void => {
    const overlay = requireLoadingOverlay(host, modalRoot);
    if (visible) {
        host.removeClassName(overlay, 'u-hidden');
        return;
    }
    host.addClassName(overlay, 'u-hidden');
};

const setDownloadDisabled = (host: ExportPreviewModalHost, modalRoot: HTMLElement, disabled: boolean): void => {
    const button = requireDownloadButton(host, modalRoot);
    setControlDisabledState(button, disabled);
};

export { requireContentElement, requireTitleElement, setDownloadDisabled, setLoadingVisible };
