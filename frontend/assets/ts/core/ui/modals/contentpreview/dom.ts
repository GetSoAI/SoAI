/* SoAI - Unified content preview modal DOM helpers (required selectors only) [frontend/assets/ts/core/ui/modals/contentpreview/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS } from '@core/ui/modals/contentpreview/constants.ts';

const requireElement = (selector: string, context: HTMLElement, description: string): HTMLElement => {
    const resolved = dom.resolve(selector, context);
    if (!(resolved instanceof HTMLElement)) {
        throw new Error(`Content preview modal ${description} is missing`);
    }
    return resolved;
};

const requireButton = (selector: string, context: HTMLElement, description: string): HTMLButtonElement => {
    const resolved = requireElement(selector, context, description);
    if (!(resolved instanceof HTMLButtonElement)) {
        throw new TypeError(`Content preview modal ${description} must be an HTMLButtonElement`);
    }
    return resolved;
};

export const requireContentPreviewModalRoot = (modalRoot: HTMLElement): HTMLElement => {
    if (modalRoot.id !== CONTENT_PREVIEW_MODAL_ID) {
        throw new Error('Content preview modal root does not match expected modal id');
    }
    return modalRoot;
};

export const requireContentPreviewTitleHost = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.TITLE), modalRoot, 'title host');
};

export const requireContentPreviewHeaderColorContainer = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.COLOR_CONTAINER), modalRoot, 'header color container');
};

export const requireContentPreviewTextHost = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.TEXT_HOST), modalRoot, 'text host');
};

export const requireContentPreviewTextStatsHost = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.TEXT_STATS), modalRoot, 'text stats host');
};

export const requireContentPreviewMediaHost = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.MEDIA_HOST), modalRoot, 'media host');
};

export const requireContentPreviewFooter = (modalRoot: HTMLElement): HTMLElement => {
    return requireElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.FOOTER), modalRoot, 'footer');
};

export const requireContentPreviewFooterCloseButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.CLOSE), modalRoot, 'close button');
};

export const requireContentPreviewHeaderCloseButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.HEADER_CLOSE), modalRoot, 'header close button');
};

export const requireContentPreviewDownloadButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.DOWNLOAD), modalRoot, 'download button');
};

export const requireContentPreviewCopyButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.COPY), modalRoot, 'copy button');
};

export const requireContentPreviewAttachButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.ATTACH), modalRoot, 'attach button');
};

export const requireContentPreviewOpenSourceButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.OPEN_SOURCE), modalRoot, 'open source button');
};

export const requireContentPreviewEditButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.EDIT), modalRoot, 'edit button');
};

export const requireContentPreviewSaveButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.SAVE), modalRoot, 'save button');
};

export const requireContentPreviewEnhanceButton = (modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButton(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.ENHANCE), modalRoot, 'enhance button');
};
