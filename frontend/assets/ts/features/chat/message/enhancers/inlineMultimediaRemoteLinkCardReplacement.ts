/* SoAI - Chat feature inline multimedia remote link card replacement [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkCardReplacement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveHttpUrl } from '@core/security/public.ts';
import { createLinkCard, createTextCard } from '@features/chat/message/enhancers/inlineMultimediaCardsText.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { createInlineMediaTextOpenAction } from '@features/chat/message/enhancers/inlineMultimediaOpenAction.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { createRemoteLinkDirectPreviewCard } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkDirectCards.ts';
import { createRemoteLinkCardWithoutExcerpt, createRemoteLinkErrorCard, createRemoteLinkExcerptFailureCard, createRemoteLinkSoftFailureCard } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkCardOutcomes.ts';
import type { RemoteLinkPreview } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPayloads.ts';
import type { RemoteTextExcerptLookupResult } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPreviewLoader.ts';
import type { RemoteLinkPreviewFailureReason } from '@features/chat/message/enhancers/inlineMultimediaRequestFailure.ts';

interface RemoteLinkReplacementOptions {
    doc: Document;
    excerptByTextPreviewUrl: Map<string, RemoteTextExcerptLookupResult>;
    failureReason: RemoteLinkPreviewFailureReason | null;
    feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder;
    preview: RemoteLinkPreview | null;
    referenceUrl: string;
    tokenLabel: string;
    tokenRaw: string;
}

const resolveRemoteLinkSoftFailureTitle = (label: string, referenceUrl: string): string => {
    if (label) {
        return label;
    }
    const resolvedUrl = resolveHttpUrl(referenceUrl);
    if (resolvedUrl === null) {
        return referenceUrl;
    }
    const parsedUrl = new URL(resolvedUrl);
    return parsedUrl.hostname || referenceUrl;
};

const createInlineMultimediaRemoteLinkReplacementCard = (options: RemoteLinkReplacementOptions): HTMLElement => {
    const label = options.tokenLabel;
    const rawToken = options.tokenRaw;
    const preview = options.preview;
    const referenceUrl = options.referenceUrl;
    const unavailableMessage = i18n.t('chat.inlinePreviews.unavailableMessage');

    if (!preview) {
        if (options.failureReason === 'upstream_not_found' || options.failureReason === 'upstream_gone') {
            return createRemoteLinkErrorCard({
                doc: options.doc,
                feedbackRecorder: options.feedbackRecorder,
                message: i18n.t('chat.inlinePreviews.remoteUrlNotFoundMessage'),
                rawToken,
                reasonCode: options.failureReason,
                referenceUrl,
                title: label || referenceUrl
            });
        }
        if (options.failureReason === 'invalid_reference') {
            return createRemoteLinkErrorCard({
                doc: options.doc,
                feedbackRecorder: options.feedbackRecorder,
                message: i18n.t('chat.inlinePreviews.remoteUrlInvalidMessage'),
                rawToken,
                reasonCode: options.failureReason,
                referenceUrl,
                title: label || referenceUrl
            });
        }
        return createRemoteLinkSoftFailureCard({
            doc: options.doc,
            feedbackRecorder: options.feedbackRecorder,
            reasonCode: 'request_failed',
            referenceUrl,
            title: resolveRemoteLinkSoftFailureTitle(label, referenceUrl)
        });
    }

    const title = label || (preview.title ? preview.title : preview.sourceUrl);
    const directCard = createRemoteLinkDirectPreviewCard({
        doc: options.doc,
        preview,
        referenceUrl,
        title
    });
    if (directCard !== null) {
        return directCard;
    }
    if (preview.type !== 'link' && preview.type !== 'text') {
        return createRemoteLinkErrorCard({
            doc: options.doc,
            feedbackRecorder: options.feedbackRecorder,
            message: unavailableMessage,
            rawToken,
            reasonCode: 'unsupported',
            referenceUrl,
            title
        });
    }
    if (preview.type === 'link' && !preview.excerptAvailable) {
        return createRemoteLinkCardWithoutExcerpt({
            doc: options.doc,
            preview,
            referenceUrl,
            title
        });
    }

    const textPreviewUrl = preview.previewUrl;
    if (!textPreviewUrl) {
        if (preview.type === 'link') {
            return createRemoteLinkExcerptFailureCard({
                doc: options.doc,
                feedbackRecorder: options.feedbackRecorder,
                preview,
                reasonCode: 'request_failed',
                referenceUrl,
                title
            });
        }
        return createRemoteLinkErrorCard({
            doc: options.doc,
            feedbackRecorder: options.feedbackRecorder,
            message: unavailableMessage,
            rawToken,
            reasonCode: 'request_failed',
            referenceUrl,
            title
        });
    }

    const excerptResult = options.excerptByTextPreviewUrl.get(textPreviewUrl) ?? null;
    if (!excerptResult) {
        if (preview.type === 'link') {
            return createRemoteLinkExcerptFailureCard({
                doc: options.doc,
                feedbackRecorder: options.feedbackRecorder,
                preview,
                reasonCode: 'request_failed',
                referenceUrl,
                title
            });
        }
        return createRemoteLinkErrorCard({
            doc: options.doc,
            feedbackRecorder: options.feedbackRecorder,
            message: unavailableMessage,
            rawToken,
            reasonCode: 'request_failed',
            referenceUrl,
            title
        });
    }
    if ('errorMessage' in excerptResult) {
        if (preview.type === 'link') {
            return createRemoteLinkExcerptFailureCard({
                doc: options.doc,
                feedbackRecorder: options.feedbackRecorder,
                preview,
                reasonCode: 'request_failed',
                referenceUrl,
                title
            });
        }
        return createRemoteLinkErrorCard({
            doc: options.doc,
            feedbackRecorder: options.feedbackRecorder,
            message: excerptResult.errorMessage,
            rawToken,
            reasonCode: 'request_failed',
            referenceUrl,
            title
        });
    }

    const action: InlineMediaOpenAction = createInlineMediaTextOpenAction({
        textContent: excerptResult.excerpt,
        openSourceUrl: preview.sourceUrl,
        title,
        contentType: null,
        contentLength: null,
        sourceReference: { type: 'url', value: preview.sourceUrl }
    });

    if (preview.type === 'link') {
        return createLinkCard(options.doc, {
            title,
            referenceText: referenceUrl,
            referenceHref: referenceUrl,
            referenceLinkType: null,
            description: preview.description,
            thumbnailUrl: preview.thumbnailUrl,
            excerpt: excerptResult.excerpt,
            sourceHref: preview.sourceUrl
        });
    }
    return createTextCard(options.doc, {
        title,
        referenceText: referenceUrl,
        referenceHref: referenceUrl,
        referenceLinkType: null,
        excerpt: excerptResult.excerpt,
        openAction: action,
        sourceHref: preview.sourceUrl
    });
};

export { createInlineMultimediaRemoteLinkReplacementCard };
