/* SoAI - Chat feature inline multimedia remote link card outcomes [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkCardOutcomes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createErrorCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import { createLinkCard } from '@features/chat/message/enhancers/inlineMultimediaCardsText.ts';
import type { ContentPreviewReasonCode } from '@features/chat/contentPreviewContracts.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import type { RemoteLinkPreview } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPayloads.ts';

type RemotePageLinkPreview = Extract<RemoteLinkPreview, { type: 'link' }>;

interface RemoteLinkBaseCardOptions {
    doc: Document;
    referenceUrl: string;
    title: string;
}

interface RemoteLinkPreviewCardOptions extends RemoteLinkBaseCardOptions {
    preview: RemotePageLinkPreview;
}

interface RemoteLinkFailureCardOptions extends RemoteLinkBaseCardOptions {
    feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder;
    reasonCode: ContentPreviewReasonCode;
}

interface RemoteLinkExcerptFailureCardOptions extends RemoteLinkFailureCardOptions {
    preview: RemotePageLinkPreview;
}

interface RemoteLinkErrorCardOptions extends RemoteLinkFailureCardOptions {
    message: string;
    rawToken: string;
}

const createRemoteLinkCardWithoutExcerpt = (options: RemoteLinkPreviewCardOptions): HTMLElement => {
    return createLinkCard(options.doc, {
        title: options.title,
        referenceText: options.referenceUrl,
        referenceHref: options.referenceUrl,
        referenceLinkType: null,
        description: options.preview.description,
        thumbnailUrl: options.preview.thumbnailUrl,
        excerpt: '',
        sourceHref: options.preview.sourceUrl
    });
};

const recordRemoteLinkFailure = (options: RemoteLinkFailureCardOptions): void => {
    options.feedbackRecorder.recordFailure({
        referenceType: 'remote_url',
        target: options.referenceUrl,
        reasonCode: options.reasonCode
    });
};

const createRemoteLinkExcerptFailureCard = (options: RemoteLinkExcerptFailureCardOptions): HTMLElement => {
    recordRemoteLinkFailure(options);
    return createRemoteLinkCardWithoutExcerpt({
        doc: options.doc,
        preview: options.preview,
        referenceUrl: options.referenceUrl,
        title: options.title
    });
};

const createRemoteLinkSoftFailureCard = (options: RemoteLinkFailureCardOptions): HTMLElement => {
    recordRemoteLinkFailure(options);
    return createLinkCard(options.doc, {
        title: options.title,
        referenceText: options.referenceUrl,
        referenceHref: options.referenceUrl,
        referenceLinkType: null,
        description: null,
        thumbnailUrl: null,
        excerpt: '',
        sourceHref: options.referenceUrl
    });
};

const createRemoteLinkErrorCard = (options: RemoteLinkErrorCardOptions): HTMLElement => {
    recordRemoteLinkFailure(options);
    return createErrorCard(options.doc, options.title, options.message, {
        openFileExplorerHref: null,
        searchHref: null,
        copyValue: options.rawToken
    });
};

export { createRemoteLinkCardWithoutExcerpt, createRemoteLinkErrorCard, createRemoteLinkExcerptFailureCard, createRemoteLinkSoftFailureCard };
