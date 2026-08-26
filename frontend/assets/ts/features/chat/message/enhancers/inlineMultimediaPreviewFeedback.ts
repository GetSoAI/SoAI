/* SoAI - Assistant inline preview failure tracking for model-visible recovery [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import { recordContentPreviewFeedback } from '@features/chat/contentPreviewFeedbackState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ContentPreviewFeedbackItem, ContentPreviewReasonCode } from '@features/chat/contentPreviewContracts.ts';
import { isHTMLAnchorElementInOwnDocument, isHTMLImageElementInOwnDocument, shouldSkipInlineMediaAnchor, shouldSkipInlineMediaImage } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { collectInlineMediaTokensInContainer, type InlineMediaToken } from '@features/chat/message/enhancers/inlineMultimediaTokenParsing.ts';

const MAX_DISABLED_PREVIEW_ITEMS = 12;

type PreviewFailureReferenceType = 'absolute_path' | 'virtual_path' | 'remote_url';

interface InlineMultimediaPreviewFeedbackRecorder {
    recordFailure(inputArguments: { referenceType: PreviewFailureReferenceType; target: string; reasonCode: ContentPreviewReasonCode }): void;
}

const createInlineMultimediaPreviewFeedbackRecorder = (message: ChatMessage | null): InlineMultimediaPreviewFeedbackRecorder => {
    return {
        recordFailure: (inputArguments): void => {
            if (message === null) {
                return;
            }
            const target = toTrimmedString(inputArguments.target);
            if (!target) {
                return;
            }
            const item: ContentPreviewFeedbackItem = {
                referenceType: inputArguments.referenceType,
                target,
                status: 'failed',
                reasonCode: inputArguments.reasonCode
            };
            recordContentPreviewFeedback(message, [item]);
        }
    };
};

const recordDisabledInlineMultimediaPreviewFeedback = (message: ChatMessage | null, container: HTMLElement, tokensOverride: readonly InlineMediaToken[] | null = null): void => {
    if (message === null) {
        return;
    }
    const items: ContentPreviewFeedbackItem[] = [];
    const tokens = tokensOverride ? [...tokensOverride] : collectInlineMediaTokensInContainer(container, { maxTokens: MAX_DISABLED_PREVIEW_ITEMS });
    for (const token of tokens) {
        items.push({
            referenceType: token.type,
            target: token.target,
            status: 'disabled',
            reasonCode: 'previews_disabled'
        });
        if (items.length >= MAX_DISABLED_PREVIEW_ITEMS) {
            recordContentPreviewFeedback(message, items);
            return;
        }
    }

    const anchors = dom.resolveAll('a[href]', container);
    for (const anchor of anchors) {
        if (!isHTMLAnchorElementInOwnDocument(anchor)) {
            continue;
        }
        if (shouldSkipInlineMediaAnchor(anchor)) {
            continue;
        }
        const href = toTrimmedString(anchor.getAttribute('href') ?? '');
        if (!isAbsoluteHttpUrl(href)) {
            continue;
        }
        items.push({
            referenceType: 'remote_url',
            target: href,
            status: 'disabled',
            reasonCode: 'previews_disabled'
        });
        if (items.length >= MAX_DISABLED_PREVIEW_ITEMS) {
            recordContentPreviewFeedback(message, items);
            return;
        }
    }

    const images = dom.resolveAll('img', container);
    for (const image of images) {
        if (!isHTMLImageElementInOwnDocument(image)) {
            continue;
        }
        if (shouldSkipInlineMediaImage(image)) {
            continue;
        }
        const src = toTrimmedString(image.getAttribute('src') ?? '');
        if (!isAbsoluteHttpUrl(src)) {
            continue;
        }
        items.push({
            referenceType: 'remote_url',
            target: src,
            status: 'disabled',
            reasonCode: 'previews_disabled'
        });
        if (items.length >= MAX_DISABLED_PREVIEW_ITEMS) {
            recordContentPreviewFeedback(message, items);
            return;
        }
    }

    recordContentPreviewFeedback(message, items);
};

export { MAX_DISABLED_PREVIEW_ITEMS, createInlineMultimediaPreviewFeedbackRecorder, recordDisabledInlineMultimediaPreviewFeedback };
export type { InlineMultimediaPreviewFeedbackRecorder, PreviewFailureReferenceType };
