/* SoAI - Inline multimedia DOM work detection [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaWorkDetection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { DISABLED_INLINE_MULTIMEDIA_SELECTOR, ENABLED_INLINE_MULTIMEDIA_SELECTOR } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';
import { PREVIEW_REFERENCE_START } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

const containsElementMatching = (container: HTMLElement, selector: string): boolean => {
    return container.matches(selector) || dom.resolve(selector, container) !== null;
};

const containsRawInlinePreviewToken = (container: HTMLElement): boolean => {
    return container.textContent?.includes(PREVIEW_REFERENCE_START) === true;
};

const mayContainEnabledInlineMultimediaWork = (container: HTMLElement, allowImplicitRemoteUrlCards: boolean): boolean => {
    if (containsElementMatching(container, ENABLED_INLINE_MULTIMEDIA_SELECTOR)) {
        return true;
    }
    if (allowImplicitRemoteUrlCards && containsElementMatching(container, 'a[href]')) {
        return true;
    }
    return containsRawInlinePreviewToken(container);
};

const mayContainDisabledInlineMultimediaReferences = (container: HTMLElement): boolean => {
    return containsElementMatching(container, DISABLED_INLINE_MULTIMEDIA_SELECTOR) || containsRawInlinePreviewToken(container);
};

export { containsRawInlinePreviewToken, mayContainDisabledInlineMultimediaReferences, mayContainEnabledInlineMultimediaWork };
