/* SoAI - Chat feature multimedia preview dataset [frontend/assets/ts/features/chat/message/multimediaPreviewDataset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalBooleanFlagFromString, parseNonNegativeIntegerFromString } from '@core/dom/attributes.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttributes } from '@core/security/uiHtml.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { isInlineMediaOpenActionType, type InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { applyChatMultimediaPreviewSourceReferenceDataset, readChatMultimediaPreviewSourceReference, renderChatMultimediaPreviewSourceReferenceAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl } from '@features/chat/message/multimediaPreviewSourceReferenceDataset.ts';

type ChatMultimediaPreviewType = InlineMediaOpenAction['type'];

type ChatInlineMediaMetadata = Readonly<{
    contentType: string | null;
    contentLength: number | null;
}>;

type ChatMultimediaPreviewDataset = Readonly<{
    type: ChatMultimediaPreviewType;
    title: string;
    previewUrl: string | null;
    textContent: string | null;
    openSourceUrl: string | null;
    downloadName: string | null;
    downloadUrl: string | null;
    contentType: string | null;
    contentLength: number | null;
    sourceReference: ContentPreviewSourceReference | null;
    requireMetadata: boolean;
}>;

type ChatMultimediaPreviewDatasetDescriptor = Readonly<{
    datasetKey: string;
    attributeName: string;
}>;

const CHAT_MULTIMEDIA_PREVIEW_DATASET = Object.freeze({
    action: { datasetKey: 'action', attributeName: 'data-action' },
    type: { datasetKey: 'mediaType', attributeName: 'data-media-type' },
    title: { datasetKey: 'mediaTitle', attributeName: 'data-media-title' },
    openSourceUrl: { datasetKey: 'mediaOpenSourceUrl', attributeName: 'data-media-open-source-url' },
    textContent: { datasetKey: 'mediaTextContent', attributeName: 'data-media-text-content' },
    previewUrl: { datasetKey: 'mediaPreviewUrl', attributeName: 'data-media-preview-url' },
    downloadName: { datasetKey: 'mediaDownloadName', attributeName: 'data-media-download-name' },
    downloadUrl: { datasetKey: 'mediaDownloadUrl', attributeName: 'data-media-download-url' },
    requireMetadata: { datasetKey: 'mediaRequireMetadata', attributeName: 'data-media-require-metadata' },
    contentType: { datasetKey: 'mediaContentType', attributeName: 'data-media-content-type' },
    contentLength: { datasetKey: 'mediaContentLength', attributeName: 'data-media-content-length' }
} satisfies Record<string, ChatMultimediaPreviewDatasetDescriptor>);

const readOptionalNonNegativeIntegerDatasetMediaContentLength = (element: HTMLElement): number | null => {
    const raw = element.dataset['mediaContentLength'];
    if (raw === undefined) {
        return null;
    }
    const trimmed = raw.trim();
    if (!trimmed) {
        return null;
    }
    return parseNonNegativeIntegerFromString(trimmed, 'Chat multimedia preview data-media-content-length');
};

const createChatInlineMediaMetadata = (contentType: string | null, contentLength: number | null, requireMetadata: boolean): ChatInlineMediaMetadata => {
    if (requireMetadata && (contentType === null || contentLength === null)) {
        throw new Error('Chat multimedia preview metadata contract violation: required content metadata is missing for this card.');
    }
    return Object.freeze({
        contentType,
        contentLength
    });
};

const readChatMultimediaPreviewDataset = (actionElement: HTMLElement): ChatMultimediaPreviewDataset => {
    const typeValue = toTrimmedString(actionElement.dataset['mediaType'] ?? '');
    if (!typeValue) {
        throw new Error('Chat multimedia preview requires data-media-type');
    }
    if (!isInlineMediaOpenActionType(typeValue)) {
        throw new Error(`Unhandled chat multimedia preview type: "${typeValue}"`);
    }
    const type: ChatMultimediaPreviewType = typeValue;

    const title = toTrimmedString(actionElement.dataset['mediaTitle'] ?? '');
    const openSourceUrl = toTrimmedString(actionElement.dataset['mediaOpenSourceUrl'] ?? '') || null;
    const downloadName = toTrimmedString(actionElement.dataset['mediaDownloadName'] ?? '') || null;
    const downloadUrl = toTrimmedString(actionElement.dataset['mediaDownloadUrl'] ?? '') || null;
    const previewUrl = toTrimmedString(actionElement.dataset['mediaPreviewUrl'] ?? '') || null;
    const textContentRaw = actionElement.dataset['mediaTextContent'];
    const textContent = textContentRaw === undefined ? null : textContentRaw;
    const contentType = toTrimmedString(actionElement.dataset['mediaContentType'] ?? '') || null;
    const contentLength = readOptionalNonNegativeIntegerDatasetMediaContentLength(actionElement);
    const sourceReference = readChatMultimediaPreviewSourceReference(actionElement);

    const requireMetadataRaw = actionElement.dataset['mediaRequireMetadata'];
    const requireMetadata = requireMetadataRaw === undefined ? false : optionalBooleanFlagFromString(requireMetadataRaw);
    createChatInlineMediaMetadata(contentType, contentLength, requireMetadata);

    if (type === 'text') {
        if (textContent === null) {
            throw new Error('Chat multimedia preview requires data-media-text-content for text previews');
        }
        return {
            type,
            title,
            previewUrl: null,
            textContent,
            openSourceUrl,
            downloadName: null,
            downloadUrl: null,
            contentType,
            contentLength,
            sourceReference,
            requireMetadata
        };
    }

    if (previewUrl === null) {
        throw new Error(`Chat multimedia preview requires data-media-preview-url for ${type}`);
    }

    return {
        type,
        title,
        previewUrl,
        textContent: null,
        openSourceUrl,
        downloadName,
        downloadUrl,
        contentType,
        contentLength,
        sourceReference,
        requireMetadata
    };
};

const requireChatMultimediaPreviewUrl = (dataset: ChatMultimediaPreviewDataset, label: string): string => {
    if (dataset.previewUrl === null) {
        throw new Error(`Chat multimedia preview requires data-media-preview-url for ${label}`);
    }
    return dataset.previewUrl;
};

const createChatMultimediaPreviewMetadata = (dataset: ChatMultimediaPreviewDataset): ChatInlineMediaMetadata => createChatInlineMediaMetadata(dataset.contentType, dataset.contentLength, dataset.requireMetadata);

const applyChatMultimediaPreviewOpenActionDataset = (element: HTMLElement, action: InlineMediaOpenAction): void => {
    const type = action.type;
    if (!isInlineMediaOpenActionType(type)) {
        throw new Error(`Chat multimedia preview open action has an unsupported type: "${type}".`);
    }
    element.dataset.action = CHAT_ACTIONS.OPEN_MULTIMEDIA_PREVIEW;
    element.dataset['mediaType'] = type;
    element.dataset['mediaTitle'] = action.title;
    element.dataset['mediaOpenSourceUrl'] = action.openSourceUrl;
    applyChatMultimediaPreviewSourceReferenceDataset(element, action.sourceReference);

    if (type === 'text') {
        element.dataset['mediaTextContent'] = action.textContent;
        delete element.dataset['mediaPreviewUrl'];
        delete element.dataset['mediaDownloadName'];
        delete element.dataset['mediaDownloadUrl'];
        delete element.dataset['mediaRequireMetadata'];
    } else {
        element.dataset['mediaPreviewUrl'] = action.previewUrl;
        delete element.dataset['mediaTextContent'];
        if (action.requireMetadata) {
            element.dataset['mediaRequireMetadata'] = '1';
        } else {
            delete element.dataset['mediaRequireMetadata'];
        }
        if (action.downloadName) {
            element.dataset['mediaDownloadName'] = action.downloadName;
        } else {
            delete element.dataset['mediaDownloadName'];
        }
        if (action.downloadUrl) {
            element.dataset['mediaDownloadUrl'] = action.downloadUrl;
        } else {
            delete element.dataset['mediaDownloadUrl'];
        }
    }

    if (action.contentType) {
        element.dataset['mediaContentType'] = action.contentType;
    } else {
        delete element.dataset['mediaContentType'];
    }

    if (action.contentLength !== null && Number.isFinite(action.contentLength) && action.contentLength >= 0) {
        element.dataset['mediaContentLength'] = String(Math.trunc(action.contentLength));
    } else {
        delete element.dataset['mediaContentLength'];
    }
};

const renderChatMultimediaPreviewOpenActionAttributes = (action: InlineMediaOpenAction): TrustedHtml => {
    const type = action.type;
    if (!isInlineMediaOpenActionType(type)) {
        throw new Error(`Chat multimedia preview open action has an unsupported type: "${type}".`);
    }

    const sharedAttributes = uiAttributes({
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.action.attributeName]: CHAT_ACTIONS.OPEN_MULTIMEDIA_PREVIEW,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.type.attributeName]: type,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.title.attributeName]: action.title,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.openSourceUrl.attributeName]: action.openSourceUrl,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.contentType.attributeName]: action.contentType,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.contentLength.attributeName]: action.contentLength !== null && Number.isFinite(action.contentLength) && action.contentLength >= 0 ? String(Math.trunc(action.contentLength)) : undefined
    });
    const sourceAttributes = renderChatMultimediaPreviewSourceReferenceAttributes(action.sourceReference);

    if (type === 'text') {
        return joinUiHtml([sharedAttributes, sourceAttributes, uiAttributes({ [CHAT_MULTIMEDIA_PREVIEW_DATASET.textContent.attributeName]: action.textContent })]);
    }

    const imageAttributes = uiAttributes({
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.previewUrl.attributeName]: action.previewUrl,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.downloadName.attributeName]: action.downloadName,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.downloadUrl.attributeName]: action.downloadUrl,
        [CHAT_MULTIMEDIA_PREVIEW_DATASET.requireMetadata.attributeName]: action.requireMetadata ? '1' : undefined
    });
    return joinUiHtml([sharedAttributes, sourceAttributes, imageAttributes]);
};

export { CHAT_MULTIMEDIA_PREVIEW_DATASET, applyChatMultimediaPreviewOpenActionDataset, createChatMultimediaPreviewMetadata, readChatMultimediaPreviewDataset, renderChatMultimediaPreviewOpenActionAttributes, requireChatMultimediaPreviewUrl, resolveChatMultimediaPreviewSourceReferenceForUrl };
export type { ChatInlineMediaMetadata, ChatMultimediaPreviewDataset, ChatMultimediaPreviewType };
