/* SoAI - Chat feature file preview item document markup [frontend/assets/ts/features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';

type ChatFilePreviewItemDocumentMarkupArguments = {
    nameHtml: TrustedHtml;
    statusHtml: TrustedHtml;
    showSpinner: boolean;
    actionButtonMarkup: TrustedHtml;
    soaiPathLink?: boolean;
};

const buildChatFilePreviewItemDocumentMarkup = (inputArguments: ChatFilePreviewItemDocumentMarkupArguments): TrustedHtml => {
    const { nameHtml, statusHtml, showSpinner, actionButtonMarkup, soaiPathLink } = inputArguments;
    const spinner = showSpinner ? uiHtml`<span class="loading-spinner file-status-spinner" aria-hidden="true"></span>` : uiHtml``;
    if (soaiPathLink === true) {
        return uiHtml`<div class="file-preview-item document soai-path-link glass-surface-light glass-surface--bordered glass-surface--rounded"><div class="file-info"><span class="file-name">${nameHtml}</span><span class="file-status">${spinner}${statusHtml}</span></div>${actionButtonMarkup}</div>`;
    }
    return uiHtml`<div class="file-preview-item document glass-surface-light glass-surface--bordered glass-surface--rounded"><div class="file-info"><span class="file-name">${nameHtml}</span><span class="file-status">${spinner}${statusHtml}</span></div>${actionButtonMarkup}</div>`;
};

export type { ChatFilePreviewItemDocumentMarkupArguments };
export { buildChatFilePreviewItemDocumentMarkup };
