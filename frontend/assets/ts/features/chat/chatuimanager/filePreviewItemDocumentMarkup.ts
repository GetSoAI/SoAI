/* SoAI - Chat feature file preview item document markup [frontend/assets/ts/features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';

type ChatFilePreviewItemDocumentMarkupArguments = {
    leadingVisualMarkup?: TrustedHtml;
    interactiveBodyAttributesMarkup?: TrustedHtml | undefined;
    interactiveBodyLabel?: string;
    nameHtml: TrustedHtml;
    statusHtml: TrustedHtml;
    showSpinner: boolean;
    actionButtonMarkup: TrustedHtml;
    soaiPathLink?: boolean;
};

const buildChatFilePreviewItemDocumentMarkup = (inputArguments: ChatFilePreviewItemDocumentMarkupArguments): TrustedHtml => {
    const { leadingVisualMarkup = uiHtml``, interactiveBodyAttributesMarkup, interactiveBodyLabel, nameHtml, statusHtml, showSpinner, actionButtonMarkup, soaiPathLink } = inputArguments;
    const spinner = showSpinner ? uiHtml`<span class="loading-spinner file-status-spinner" aria-hidden="true"></span>` : uiHtml``;
    const content = uiHtml`${leadingVisualMarkup}<span class="file-info"><span class="file-name">${nameHtml}</span><span class="file-status">${spinner}${statusHtml}</span></span>`;
    if (interactiveBodyAttributesMarkup !== undefined) {
        if (interactiveBodyLabel === undefined || !interactiveBodyLabel.trim()) throw new Error('Interactive attachment preview rows require a label');
        const linkClass = soaiPathLink === true ? ' soai-path-link' : '';
        return uiHtml`<div class="file-preview-item document chat-attachment-summary-card--removable${linkClass} glass-surface-light glass-surface--bordered glass-surface--rounded"><button type="button" class="chat-attachment-summary-card-body"${interactiveBodyAttributesMarkup} aria-label="${uiAttr(interactiveBodyLabel)}" data-tooltip="${uiAttr(interactiveBodyLabel)}">${content}</button>${actionButtonMarkup}</div>`;
    }
    if (soaiPathLink === true) {
        return uiHtml`<div class="file-preview-item document soai-path-link glass-surface-light glass-surface--bordered glass-surface--rounded">${content}${actionButtonMarkup}</div>`;
    }
    return uiHtml`<div class="file-preview-item document glass-surface-light glass-surface--bordered glass-surface--rounded">${content}${actionButtonMarkup}</div>`;
};

export type { ChatFilePreviewItemDocumentMarkupArguments };
export { buildChatFilePreviewItemDocumentMarkup };
