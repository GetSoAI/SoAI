/* SoAI - Chat multimedia preview source reference dataset mapping [frontend/assets/ts/features/chat/message/multimediaPreviewSourceReferenceDataset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isAbsoluteHttpUrl, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttributes } from '@core/security/uiHtml.ts';
import { normalizeContentPreviewSourceReference } from '@core/ui/modals/contentpreview/sourceReference.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import { normalizeConversationVirtualPathValue } from '@features/chat/validation/soaiPathValues.ts';

type ChatMultimediaPreviewSourceDatasetDescriptor = Readonly<{
    datasetKey: string;
    attributeName: string;
}>;

const CHAT_MULTIMEDIA_PREVIEW_SOURCE_DATASET = Object.freeze({
    sourceType: { datasetKey: 'mediaSourceType', attributeName: 'data-media-source-type' },
    sourceValue: { datasetKey: 'mediaSourceValue', attributeName: 'data-media-source-value' },
    sourceConversationId: { datasetKey: 'mediaSourceConversationId', attributeName: 'data-media-source-conversation-id' },
    sourceRootFingerprint: { datasetKey: 'mediaSourceRootFingerprint', attributeName: 'data-media-source-root-fingerprint' }
} satisfies Record<string, ChatMultimediaPreviewSourceDatasetDescriptor>);

const isDataUrl = (value: string): boolean => value.trim().toLowerCase().startsWith('data:');

const resolveChatMultimediaPreviewSourceReferenceForUrl = (value: string): ContentPreviewSourceReference | null => {
    const trimmed = toTrimmedString(value);
    if (!trimmed || isDataUrl(trimmed)) {
        return null;
    }
    if (isAbsoluteHttpUrl(trimmed)) {
        return Object.freeze({ type: 'url', value: trimmed });
    }
    return Object.freeze({ type: 'path', value: trimmed });
};

const normalizeChatMultimediaPreviewSourceReference = (sourceReference: ContentPreviewSourceReference | null): ContentPreviewSourceReference | null => {
    if (sourceReference === null || isDataUrl(sourceReference.value)) {
        return null;
    }
    const normalized = normalizeContentPreviewSourceReference(sourceReference);
    if (normalized === null || normalized.type !== 'conversation_soai_path') {
        return normalized;
    }
    const canonicalValue = normalizeConversationVirtualPathValue(normalized.value);
    if (canonicalValue === null) {
        throw new Error('Chat multimedia preview conversation SoAI path source value must be canonical');
    }
    return Object.freeze({
        type: 'conversation_soai_path',
        conversationId: normalized.conversationId,
        rootFingerprint: normalized.rootFingerprint,
        value: canonicalValue
    });
};

const readChatMultimediaPreviewSourceReference = (actionElement: HTMLElement): ContentPreviewSourceReference | null => {
    const type = toTrimmedString(actionElement.dataset['mediaSourceType'] ?? '');
    const value = toTrimmedString(actionElement.dataset['mediaSourceValue'] ?? '');
    const conversationId = toTrimmedString(actionElement.dataset['mediaSourceConversationId'] ?? '');
    const rootFingerprint = toTrimmedString(actionElement.dataset['mediaSourceRootFingerprint'] ?? '');
    if (!type && !value && !conversationId && !rootFingerprint) {
        return null;
    }
    if (!value) {
        throw new Error('Chat multimedia preview data-media-source-value is required when data-media-source-type is set');
    }
    if (type === 'conversation_soai_path') {
        return normalizeChatMultimediaPreviewSourceReference(Object.freeze({ type, value, conversationId, rootFingerprint }));
    }
    if (conversationId || rootFingerprint) {
        throw new Error('Chat multimedia preview conversation source fields require data-media-source-type conversation_soai_path');
    }
    if (type !== 'path' && type !== 'url') {
        throw new Error('Chat multimedia preview data-media-source-type must be path, url, or conversation_soai_path');
    }
    return normalizeChatMultimediaPreviewSourceReference(Object.freeze({ type, value }));
};

const applyChatMultimediaPreviewSourceReferenceDataset = (element: HTMLElement, sourceReference: ContentPreviewSourceReference | null): void => {
    const normalized = normalizeChatMultimediaPreviewSourceReference(sourceReference);
    if (normalized === null) {
        delete element.dataset['mediaSourceType'];
        delete element.dataset['mediaSourceValue'];
        delete element.dataset['mediaSourceConversationId'];
        delete element.dataset['mediaSourceRootFingerprint'];
        return;
    }
    element.dataset['mediaSourceType'] = normalized.type;
    element.dataset['mediaSourceValue'] = normalized.value;
    if (normalized.type === 'conversation_soai_path') {
        element.dataset['mediaSourceConversationId'] = normalized.conversationId;
        element.dataset['mediaSourceRootFingerprint'] = normalized.rootFingerprint;
        return;
    }
    delete element.dataset['mediaSourceConversationId'];
    delete element.dataset['mediaSourceRootFingerprint'];
};

const renderChatMultimediaPreviewSourceReferenceAttributes = (sourceReference: ContentPreviewSourceReference | null): TrustedHtml => {
    const normalized = normalizeChatMultimediaPreviewSourceReference(sourceReference);
    if (normalized === null) {
        return EMPTY_UI_HTML;
    }
    return uiAttributes({
        [CHAT_MULTIMEDIA_PREVIEW_SOURCE_DATASET.sourceType.attributeName]: normalized.type,
        [CHAT_MULTIMEDIA_PREVIEW_SOURCE_DATASET.sourceValue.attributeName]: normalized.value,
        [CHAT_MULTIMEDIA_PREVIEW_SOURCE_DATASET.sourceConversationId.attributeName]: normalized.type === 'conversation_soai_path' ? normalized.conversationId : undefined,
        [CHAT_MULTIMEDIA_PREVIEW_SOURCE_DATASET.sourceRootFingerprint.attributeName]: normalized.type === 'conversation_soai_path' ? normalized.rootFingerprint : undefined
    });
};

export { applyChatMultimediaPreviewSourceReferenceDataset, readChatMultimediaPreviewSourceReference, renderChatMultimediaPreviewSourceReferenceAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl };
