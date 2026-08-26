/* SoAI - Chat SoAI path content preview [frontend/assets/ts/features/chat/message/soaiPathContentPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { buildFileExplorerDeepLink } from '@core/fileexplorerbrowser/deepLinks.ts';
import { basenameVirtualPath, parentVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { copySoaiPathTokenToClipboard } from '@core/fileexplorerbrowser/soaiPathClipboard.ts';
import { i18n } from '@core/i18n/index.ts';
import { createDocumentContentPreviewRequest, createMediaContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewOpenRequest } from '@core/ui/modals/contentpreview/types.ts';
import type { ChatSoaiPathsApi } from '@features/chat/pagecontracts/types.ts';
import type { SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { copyChatMessageTextWithFeedback, type ChatMessageCopyFeedbackDependencies, type CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import { buildSourceReference, parseFolderEntriesText, parseOpenVirtualPath, parseSoaiPathToken, requireSoaiPathContentPart, resolveContentLength, resolveContentType, resolvePreviewType } from '@features/chat/message/soaiPathContentPreviewPayload.ts';

type ChatSoaiPathContentPreviewDependencies = CopyActionDependencies & {
    soaiPathsApi: Pick<ChatSoaiPathsApi, 'preview' | 'read' | 'download' | 'open' | 'token'>;
};

type ChatSoaiPathContentPreviewOpenArguments = {
    conversationId: string;
    title: string;
    contentPart: SoaiPathStoragePart;
    isCurrent: () => boolean;
};

const isUnavailableDownloadResponse = (response: Response): boolean => {
    const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
    return !response.ok || contentType.includes('application/json');
};

class ChatSoaiPathContentPreview {
    readonly #soaiPathsApi: Pick<ChatSoaiPathsApi, 'preview' | 'read' | 'download' | 'open' | 'token'>;
    readonly #runWithBoundary: CopyActionDependencies['runWithBoundary'];
    readonly #copyFeedback: ChatMessageCopyFeedbackDependencies;
    #controller: AbortController | null = null;
    #objectUrl: string | null = null;
    #generation = 0;

    constructor(dependencies: ChatSoaiPathContentPreviewDependencies) {
        this.#soaiPathsApi = dependencies.soaiPathsApi;
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#copyFeedback = {
            hasClipboardSupport: dependencies.hasClipboardSupport,
            copyToClipboard: dependencies.copyToClipboard,
            showNotification: dependencies.showNotification
        };
    }

    reset(): void {
        this.#generation += 1;
        this.#controller?.abort();
        this.#controller = null;
        this.#releaseActiveObjectUrl();
    }

    open(inputArguments: ChatSoaiPathContentPreviewOpenArguments): void {
        this.reset();
        const generation = this.#generation;
        const controller = new AbortController();
        this.#controller = controller;
        terminateHandledPromise(this.#runWithBoundary('chat:soaiPathContentPreviewOpen', () => this.#runOpen(inputArguments, generation, controller.signal)));
    }

    async #runOpen(inputArguments: ChatSoaiPathContentPreviewOpenArguments, generation: number, signal: AbortSignal): Promise<void> {
        try {
            const contentPart = requireSoaiPathContentPart(inputArguments.contentPart);
            const openSourceUrl = await this.#resolveOpenSourceUrl(inputArguments.conversationId, contentPart, signal);
            if (!this.#isCurrent(inputArguments, generation, signal)) {
                return;
            }
            const request = await this.#buildRequest(inputArguments, contentPart, openSourceUrl, generation, signal);
            if (!this.#isCurrent(inputArguments, generation, signal)) {
                this.#releaseActiveObjectUrl();
                return;
            }
            requireContentPreviewModalService().open(request);
        } catch (error) {
            this.#releaseActiveObjectUrl();
            if (isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        }
    }

    async #resolveOpenSourceUrl(conversationId: string, contentPart: SoaiPathStoragePart, signal: AbortSignal): Promise<string | null> {
        const payload = await this.#runWithBoundary('chat:soaiPathContentPreviewOpenSource', () => this.#soaiPathsApi.open(conversationId, { contentPart: contentPart }, { signal }));
        const virtualPath = parseOpenVirtualPath(payload);
        return virtualPath === null ? null : buildFileExplorerDeepLink({ directoryPath: parentVirtualPath(virtualPath), highlightPath: virtualPath, search: basenameVirtualPath(virtualPath) });
    }

    async #buildRequest(inputArguments: ChatSoaiPathContentPreviewOpenArguments, contentPart: SoaiPathStoragePart, openSourceUrl: string | null, generation: number, signal: AbortSignal): Promise<ContentPreviewOpenRequest> {
        const sourceReference = buildSourceReference(inputArguments.conversationId, contentPart);
        const previewType = resolvePreviewType(contentPart);
        if (previewType === 'text' || contentPart.entryType === 'folder') {
            const content = contentPart.entryType === 'folder' ? await this.#readFolderPreview(inputArguments.conversationId, contentPart, signal) : await this.#readTextPreview(inputArguments.conversationId, contentPart, signal);
            return createTextContentPreviewRequest({ scope: 'chat', headerDescription: i18n.t('chat.attachments.badge.soaiLink'), sourceReference, openSourceUrl, externalOpenBehavior: 'neverConfirm', type: 'text', baseline: { title: inputArguments.title, content, promptColor: null }, editable: false, languageMode: 'default', disableCopyWhenEmpty: true, disableDownloadWhenEmpty: true, colorToolkit: null, onRequestSave: null, onRequestDownload: () => this.#download(inputArguments, contentPart, generation, signal), onRequestCopy: async (text) => await copyChatMessageTextWithFeedback(this.#copyFeedback, text), onRequestAttach: () => this.#copyToken(inputArguments, contentPart, generation, signal), enhance: null, onStatePotentiallyChanged: null });
        }
        if (previewType === 'image' || previewType === 'audio' || previewType === 'video') {
            const sourceUrl = await this.#createObjectUrl(inputArguments, contentPart, generation, signal);
            return createMediaContentPreviewRequest({ scope: 'chat', headerDescription: i18n.t('chat.attachments.badge.soaiLink'), sourceReference, openSourceUrl, externalOpenBehavior: 'neverConfirm', type: previewType, title: inputArguments.title, sourceUrl, imageMetadata: { contentType: resolveContentType(contentPart), contentLength: resolveContentLength(contentPart) }, onRequestDownload: () => this.#download(inputArguments, contentPart, generation, signal), onRequestAttach: () => this.#copyToken(inputArguments, contentPart, generation, signal), onSourceUrlRelease: () => this.#releaseObjectUrl(sourceUrl) });
        }
        const type = previewType === 'document' ? 'document' : 'file';
        return createDocumentContentPreviewRequest({ scope: 'chat', headerDescription: i18n.t('chat.attachments.badge.soaiLink'), sourceReference, openSourceUrl, externalOpenBehavior: 'neverConfirm', type, title: inputArguments.title, onRequestDownload: () => this.#download(inputArguments, contentPart, generation, signal), onRequestAttach: () => this.#copyToken(inputArguments, contentPart, generation, signal) });
    }

    async #readTextPreview(conversationId: string, contentPart: SoaiPathStoragePart, signal: AbortSignal): Promise<string> {
        const payload = await this.#runWithBoundary('chat:soaiPathContentPreviewRead', () => this.#soaiPathsApi.read(conversationId, { contentPart: contentPart }, { signal }));
        return payload.state === 'available' ? payload.text : '';
    }

    async #readFolderPreview(conversationId: string, contentPart: SoaiPathStoragePart, signal: AbortSignal): Promise<string> {
        const payload = await this.#runWithBoundary('chat:soaiPathContentPreviewFolder', () => this.#soaiPathsApi.preview(conversationId, { contentPart: contentPart }, { signal }));
        return parseFolderEntriesText(payload);
    }

    async #createObjectUrl(inputArguments: ChatSoaiPathContentPreviewOpenArguments, contentPart: SoaiPathStoragePart, generation: number, signal: AbortSignal): Promise<string> {
        const response = await this.#runWithBoundary('chat:soaiPathContentPreviewDownload', () => this.#soaiPathsApi.download(inputArguments.conversationId, { contentPart: contentPart }, { rawResponse: true, signal }));
        if (!(typeof Response === 'function' && response instanceof Response)) {
            throw new Error('SoAI path download did not return a Response');
        }
        if (isUnavailableDownloadResponse(response)) {
            throw new Error('SoAI path media preview is unavailable');
        }
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            throw createAbortError('Operation aborted');
        }
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            URL.revokeObjectURL(objectUrl);
            throw createAbortError('Operation aborted');
        }
        this.#objectUrl = objectUrl;
        return objectUrl;
    }

    #releaseActiveObjectUrl(): void {
        if (this.#objectUrl !== null) {
            URL.revokeObjectURL(this.#objectUrl);
            this.#objectUrl = null;
        }
    }

    #releaseObjectUrl(objectUrl: string): void {
        if (this.#objectUrl !== objectUrl) {
            return;
        }
        URL.revokeObjectURL(objectUrl);
        this.#objectUrl = null;
    }

    async #download(inputArguments: ChatSoaiPathContentPreviewOpenArguments, contentPart: SoaiPathStoragePart, generation: number, signal: AbortSignal): Promise<void> {
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            throw createAbortError('Operation aborted');
        }
        const response = await this.#runWithBoundary('chat:soaiPathContentPreviewDownload', () => this.#soaiPathsApi.download(inputArguments.conversationId, { contentPart: contentPart }, { rawResponse: true, signal }));
        if (!(typeof Response === 'function' && response instanceof Response)) {
            throw new Error('SoAI path download did not return a Response');
        }
        if (isUnavailableDownloadResponse(response)) {
            throw new Error('SoAI path download is unavailable');
        }
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            throw createAbortError('Operation aborted');
        }
        await downloadAuthenticatedResponse(response, { filename: inputArguments.title });
    }

    async #copyToken(inputArguments: ChatSoaiPathContentPreviewOpenArguments, contentPart: SoaiPathStoragePart, generation: number, signal: AbortSignal): Promise<void> {
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            throw createAbortError('Operation aborted');
        }
        const payload = await this.#runWithBoundary('chat:soaiPathContentPreviewToken', () => this.#soaiPathsApi.token(inputArguments.conversationId, { contentPart: contentPart }, { signal }));
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            throw createAbortError('Operation aborted');
        }
        await copySoaiPathTokenToClipboard(parseSoaiPathToken(payload));
    }

    #isCurrent(inputArguments: ChatSoaiPathContentPreviewOpenArguments, generation: number, signal: AbortSignal): boolean {
        return !signal.aborted && this.#generation === generation && inputArguments.isCurrent();
    }
}

export { ChatSoaiPathContentPreview };
export type { ChatSoaiPathContentPreviewOpenArguments };
