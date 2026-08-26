/* SoAI - Chat page multimedia preview action controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatMultimediaPreviewActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalClosestElement } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import type { SoaiPathOperationRequest, SoaiPathTokenResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { mapChatMultimediaPreviewDatasetToContentPreviewRequest, readChatMultimediaPreviewDataset } from '@features/chat/public.ts';

interface ChatMultimediaPreviewActionHost {
    hasClipboardSupport(): boolean;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    showNotification(message: string, type: NotificationType): void;
    requestConversationSoaiPathToken(conversationId: string, payload: SoaiPathOperationRequest): Promise<SoaiPathTokenResponse>;
}

const pauseInlineMediaForPreview = (actionElement: HTMLElement, type: 'audio' | 'video'): void => {
    const card = optionalClosestElement(actionElement, `.chat-inline-media-card--${type}.chat-inline-media-card`);
    if (!(card instanceof HTMLElement)) {
        return;
    }
    const mediaCandidate = dom.resolve(type, card);
    if (mediaCandidate === null) {
        throw new Error(`Chat multimedia preview ${type} action requires an inline ${type} element`);
    }
    if (!(mediaCandidate instanceof HTMLMediaElement)) {
        throw new Error(`Chat multimedia preview ${type} action requires a media element`);
    }
    if (mediaCandidate.paused) {
        return;
    }
    mediaCandidate.pause();
};

const handleOpenMultimediaPreviewAction = (host: ChatMultimediaPreviewActionHost, actionElement: HTMLElement): void => {
    const dataset = readChatMultimediaPreviewDataset(actionElement);
    const mapping = mapChatMultimediaPreviewDatasetToContentPreviewRequest({
        dataset,
        host,
        pauseInlineMedia: () => {
            if (dataset.type === 'audio' || dataset.type === 'video') {
                pauseInlineMediaForPreview(actionElement, dataset.type);
            }
        }
    });
    mapping.beforeOpen();
    requireContentPreviewModalService().open(mapping.request);
};

export { handleOpenMultimediaPreviewAction };
export type { ChatMultimediaPreviewActionHost };
