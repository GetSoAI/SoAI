/* SoAI - Chat multimedia content preview request mapper [frontend/assets/ts/features/chat/message/multimediaPreviewRequestMapper.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { copySoaiPathLinkToClipboard, copySoaiPathTokenToClipboard } from '@core/fileexplorerbrowser/soaiPathClipboard.ts';
import { triggerDownloadLink } from '@core/primitives/download.ts';
import type { SoaiPathOperationRequest, SoaiPathTokenResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { resolveChatPreviewHeaderDescription } from '@core/ui/modals/contentpreview/headerDescriptions.ts';
import { createMediaContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import type { ContentPreviewConversationSoaiPathSourceReference, ContentPreviewImageMetadata, ContentPreviewOpenRequest } from '@core/ui/modals/contentpreview/types.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { copyChatMessageTextWithFeedback } from '@features/chat/message/messageCopyNotifications.ts';
import { createChatMultimediaPreviewMetadata, requireChatMultimediaPreviewUrl, type ChatMultimediaPreviewDataset } from '@features/chat/message/multimediaPreviewDataset.ts';
import { normalizeConversationVirtualPathValue } from '@features/chat/validation/soaiPathValues.ts';

type ChatMultimediaPreviewRequestHost = Readonly<{
    hasClipboardSupport: () => boolean;
    copyToClipboard: (text: string, options?: { notify?: (message: string, type: NotificationType) => void }) => Promise<void>;
    showNotification: (message: string, type: NotificationType) => void;
    requestConversationSoaiPathToken: (conversationId: string, payload: SoaiPathOperationRequest) => Promise<SoaiPathTokenResponse>;
}>;

type ChatMultimediaPreviewRequestMapping = Readonly<{
    request: ContentPreviewOpenRequest;
    beforeOpen: () => void;
}>;

type ChatMultimediaPreviewRequestMapperArguments = Readonly<{
    dataset: ChatMultimediaPreviewDataset;
    host: ChatMultimediaPreviewRequestHost;
    pauseInlineMedia: () => void;
}>;

const CHAT_MULTIMEDIA_DEFAULT_DOWNLOAD_NAMES = Object.freeze({
    image: 'soai-image.png',
    audio: 'soai-audio',
    video: 'soai-video'
});

const noopBeforeContentPreviewOpen = (): void => {};

const buildConversationSoaiPathOperationPayload = (sourceReference: ContentPreviewConversationSoaiPathSourceReference): SoaiPathOperationRequest => {
    const canonicalValue = normalizeConversationVirtualPathValue(sourceReference.value);
    if (canonicalValue === null) {
        throw new Error('SoAI path preview action requires a canonical conversation virtual path');
    }
    return {
        sourceReference: { type: 'conversation_virtual_path', value: canonicalValue },
        workspaceScope: { type: 'conversation_effective_workspace', rootFingerprint: sourceReference.rootFingerprint.trim() }
    };
};

const parseSoaiPathTokenResponse = (value: SoaiPathTokenResponse): string => {
    if (value.state !== 'available') {
        throw new Error('SoAI path token is unavailable');
    }
    return value.token;
};

const createMediaMetadata = (dataset: ChatMultimediaPreviewDataset): ContentPreviewImageMetadata => {
    const metadata = createChatMultimediaPreviewMetadata(dataset);
    return Object.freeze({
        contentType: metadata.contentType,
        contentLength: metadata.contentLength
    });
};

const createAttachHandler = (dataset: ChatMultimediaPreviewDataset, host: ChatMultimediaPreviewRequestHost): (() => Promise<void>) | null => {
    const sourceReference = dataset.sourceReference;
    if (sourceReference?.type !== 'path') {
        if (sourceReference?.type !== 'conversation_soai_path') {
            return null;
        }
        return async (): Promise<void> => {
            const payload = await host.requestConversationSoaiPathToken(sourceReference.conversationId, buildConversationSoaiPathOperationPayload(sourceReference));
            await copySoaiPathTokenToClipboard(parseSoaiPathTokenResponse(payload), host);
        };
    }
    return async (): Promise<void> => {
        await copySoaiPathLinkToClipboard(sourceReference.value, host);
    };
};

const createTextCopyHandler = (host: ChatMultimediaPreviewRequestHost): ((text: string) => Promise<void>) => {
    return async (text: string): Promise<void> => {
        await copyChatMessageTextWithFeedback(
            {
                copyToClipboard: (value, options) => host.copyToClipboard(value, options),
                hasClipboardSupport: () => host.hasClipboardSupport(),
                showNotification: (message, type): void => host.showNotification(message, type)
            },
            text
        );
    };
};

const createMediaPreviewRequestMapping = (dataset: ChatMultimediaPreviewDataset, host: ChatMultimediaPreviewRequestHost, requestType: 'image' | 'audio' | 'video', pauseInlineMedia: () => void): ChatMultimediaPreviewRequestMapping => {
    const sourceUrl = requireChatMultimediaPreviewUrl(dataset, requestType);
    const downloadUrl = dataset.downloadUrl ?? sourceUrl;
    const downloadName = dataset.downloadName ?? CHAT_MULTIMEDIA_DEFAULT_DOWNLOAD_NAMES[requestType];
    const request = createMediaContentPreviewRequest({
        scope: 'chat',
        type: requestType,
        headerDescription: resolveChatPreviewHeaderDescription(requestType, dataset.contentType),
        title: dataset.title,
        sourceUrl,
        imageMetadata: createMediaMetadata(dataset),
        sourceReference: dataset.sourceReference,
        onRequestDownload: () => triggerDownloadLink({ href: downloadUrl, filename: downloadName, revokeObjectUrl: false }),
        onRequestAttach: createAttachHandler(dataset, host),
        openSourceUrl: dataset.openSourceUrl ?? sourceUrl
    });
    return Object.freeze({
        request,
        beforeOpen: requestType === 'audio' || requestType === 'video' ? pauseInlineMedia : noopBeforeContentPreviewOpen
    });
};

const createEmbedPreviewRequestMapping = (dataset: ChatMultimediaPreviewDataset, host: ChatMultimediaPreviewRequestHost): ChatMultimediaPreviewRequestMapping => {
    const sourceUrl = requireChatMultimediaPreviewUrl(dataset, 'embeds');
    return Object.freeze({
        request: createMediaContentPreviewRequest({
            scope: 'chat',
            type: 'embed',
            headerDescription: resolveChatPreviewHeaderDescription('embed', dataset.contentType),
            title: dataset.title,
            sourceUrl,
            imageMetadata: createMediaMetadata(dataset),
            sourceReference: dataset.sourceReference,
            onRequestDownload: null,
            onRequestAttach: createAttachHandler(dataset, host),
            openSourceUrl: dataset.openSourceUrl ?? sourceUrl
        }),
        beforeOpen: noopBeforeContentPreviewOpen
    });
};

const createTextPreviewRequestMapping = (dataset: ChatMultimediaPreviewDataset, host: ChatMultimediaPreviewRequestHost): ChatMultimediaPreviewRequestMapping => {
    return Object.freeze({
        request: createTextContentPreviewRequest({
            scope: 'chat',
            type: 'text',
            headerDescription: resolveChatPreviewHeaderDescription('text', dataset.contentType),
            baseline: { title: dataset.title, content: dataset.textContent ?? '', promptColor: null },
            editable: false,
            languageMode: 'default',
            disableCopyWhenEmpty: false,
            disableDownloadWhenEmpty: false,
            colorToolkit: null,
            sourceReference: dataset.sourceReference,
            onRequestSave: null,
            onRequestDownload: null,
            onRequestCopy: createTextCopyHandler(host),
            onRequestAttach: createAttachHandler(dataset, host),
            enhance: null,
            openSourceUrl: dataset.openSourceUrl,
            onStatePotentiallyChanged: null
        }),
        beforeOpen: noopBeforeContentPreviewOpen
    });
};

const mapChatMultimediaPreviewDatasetToContentPreviewRequest = ({ dataset, host, pauseInlineMedia }: ChatMultimediaPreviewRequestMapperArguments): ChatMultimediaPreviewRequestMapping => {
    if (dataset.type === 'image' || dataset.type === 'audio' || dataset.type === 'video') {
        return createMediaPreviewRequestMapping(dataset, host, dataset.type, pauseInlineMedia);
    }
    if (dataset.type === 'embed') {
        return createEmbedPreviewRequestMapping(dataset, host);
    }
    if (dataset.type === 'text') {
        return createTextPreviewRequestMapping(dataset, host);
    }
    const exhaustiveCheck: never = dataset.type;
    throw new Error(`Unhandled chat multimedia preview type: "${String(exhaustiveCheck)}"`);
};

export { mapChatMultimediaPreviewDatasetToContentPreviewRequest };
export type { ChatMultimediaPreviewRequestHost, ChatMultimediaPreviewRequestMapping };
