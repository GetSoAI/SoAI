/* SoAI - Shared UI session rendering [frontend/assets/ts/core/ui/modals/contentpreview/sessionRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyBusyState, applyButtonLabels, applyEditingUiState, applyTextEmptyDisableState } from '@core/ui/modals/contentpreview/modalButtons.ts';
import { requireContentPreviewHeaderColorContainer } from '@core/ui/modals/contentpreview/dom.ts';
import type { ContentPreviewNonTextRequest, ContentPreviewOpenRequest, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

interface ContentPreviewSessionRenderingDependencies {
    resetMedia(modalRoot: HTMLElement): void;
    resetText(modalRoot: HTMLElement): void;
    renderTextViewMode(modalRoot: HTMLElement, request: ContentPreviewTextRequest): void;
    renderMedia(modalRoot: HTMLElement, request: ContentPreviewNonTextRequest): void;
}

const clearContentPreviewHeaderColorToolkit = (modalRoot: HTMLElement, request: ContentPreviewOpenRequest | null): void => {
    if (request && request.type === 'text') {
        request.colorToolkit?.unmountHeaderColorToolkit();
    }
    requireContentPreviewHeaderColorContainer(modalRoot).textContent = '';
};

const renderContentPreviewTextMode = (dependencies: ContentPreviewSessionRenderingDependencies, modalRoot: HTMLElement, request: ContentPreviewTextRequest, previousRequest: ContentPreviewOpenRequest | null): void => {
    dependencies.resetMedia(modalRoot);
    clearContentPreviewHeaderColorToolkit(modalRoot, previousRequest);
    dependencies.renderTextViewMode(modalRoot, request);
    applyButtonLabels(modalRoot, request.labels);
    applyBusyState(modalRoot, false);
    applyTextEmptyDisableState(modalRoot, request);
    applyEditingUiState(modalRoot, request, false);
};

const renderContentPreviewMediaMode = (dependencies: ContentPreviewSessionRenderingDependencies, modalRoot: HTMLElement, request: ContentPreviewNonTextRequest, previousRequest: ContentPreviewOpenRequest | null): void => {
    clearContentPreviewHeaderColorToolkit(modalRoot, previousRequest);
    dependencies.resetText(modalRoot);
    modalRoot.setAttribute('data-page-scope', request.scope);
    delete modalRoot.dataset['promptColor'];
    modalRoot.dataset['selectedColor'] = '';
    dependencies.renderMedia(modalRoot, request);
    applyButtonLabels(modalRoot, request.labels);
    applyBusyState(modalRoot, false);
    applyEditingUiState(modalRoot, request, false);
};

export { clearContentPreviewHeaderColorToolkit, renderContentPreviewMediaMode, renderContentPreviewTextMode };
export type { ContentPreviewSessionRenderingDependencies };
