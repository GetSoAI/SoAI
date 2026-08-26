/* SoAI - Chat feature rendered markup root [frontend/assets/ts/features/chat/message/renderedMarkupRoot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';

const parseRenderedMarkupRoot = (inputArguments: { documentRef: Document; nextMarkup: TrustedHtml; context: Document | Element; failureMessage: string }): HTMLElement => {
    const parsed = parseSingleRootElement({
        documentRef: inputArguments.documentRef,
        html: inputArguments.nextMarkup,
        context: inputArguments.context
    });
    if (!(parsed instanceof HTMLElement)) {
        throw new Error(inputArguments.failureMessage);
    }
    return parsed;
};

export { parseRenderedMarkupRoot };
