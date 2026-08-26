/* SoAI - Chat SoAI file content preview [frontend/assets/ts/features/chat/message/soaiFileContentPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { triggerDownloadLink } from '@core/primitives/download.ts';
import { resolveChatPreviewHeaderDescription } from '@core/ui/modals/contentpreview/headerDescriptions.ts';
import { createDocumentContentPreviewRequest, createMediaContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { SoaiFilePreviewType } from '@features/chat/attachments/attachmentPreviewTypes.ts';
import { copyChatMessageTextWithFeedback, type ChatMessageCopyFeedbackDependencies, type CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';

type ChatSoaiFileContentPreviewDependencies = CopyActionDependencies & {
    fetchText: (url: string, signal: AbortSignal) => Promise<string>;
};

type ChatSoaiFileContentPreviewOpenArguments = {
    title: string;
    previewType: SoaiFilePreviewType;
    previewUrl: string;
    downloadUrl: string;
    contentType: string | null;
    contentLength: number | null;
    isCurrent: () => boolean;
};

class ChatSoaiFileContentPreview {
    readonly #runWithBoundary: CopyActionDependencies['runWithBoundary'];
    readonly #fetchText: (url: string, signal: AbortSignal) => Promise<string>;
    readonly #copyFeedback: ChatMessageCopyFeedbackDependencies;
    #controller: AbortController | null = null;
    #generation = 0;

    constructor(dependencies: ChatSoaiFileContentPreviewDependencies) {
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#fetchText = dependencies.fetchText;
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
    }

    open(inputArguments: ChatSoaiFileContentPreviewOpenArguments): void {
        this.reset();
        const generation = this.#generation;
        const controller = new AbortController();
        this.#controller = controller;
        terminateHandledPromise(this.#runWithBoundary('chat:soaiFileContentPreviewOpen', () => this.#runOpen(inputArguments, generation, controller.signal)));
    }

    async #runOpen(inputArguments: ChatSoaiFileContentPreviewOpenArguments, generation: number, signal: AbortSignal): Promise<void> {
        try {
            if (inputArguments.previewType === 'text') {
                await this.#openText(inputArguments, generation, signal);
                return;
            }
            if (!this.#isCurrent(inputArguments, generation, signal)) {
                return;
            }
            if (inputArguments.previewType === 'image' || inputArguments.previewType === 'audio' || inputArguments.previewType === 'video') {
                requireContentPreviewModalService().open(
                    createMediaContentPreviewRequest({
                        scope: 'chat',
                        type: inputArguments.previewType,
                        headerDescription: resolveChatPreviewHeaderDescription(inputArguments.previewType, inputArguments.contentType),
                        title: inputArguments.title,
                        sourceUrl: inputArguments.previewUrl,
                        imageMetadata: { contentType: inputArguments.contentType, contentLength: inputArguments.contentLength },
                        sourceReference: null,
                        onRequestDownload: () => triggerDownloadLink({ href: inputArguments.downloadUrl, filename: inputArguments.title, revokeObjectUrl: false }),
                        onRequestAttach: null,
                        openSourceUrl: inputArguments.downloadUrl
                    })
                );
                return;
            }
            requireContentPreviewModalService().open(
                createDocumentContentPreviewRequest({
                    scope: 'chat',
                    type: inputArguments.previewType === 'document' ? 'document' : 'file',
                    headerDescription: resolveChatPreviewHeaderDescription(inputArguments.previewType, inputArguments.contentType),
                    title: inputArguments.title,
                    sourceReference: null,
                    onRequestDownload: () => triggerDownloadLink({ href: inputArguments.downloadUrl, filename: inputArguments.title, revokeObjectUrl: false }),
                    onRequestAttach: null,
                    openSourceUrl: inputArguments.downloadUrl
                })
            );
        } catch (error) {
            if (isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        }
    }

    async #openText(inputArguments: ChatSoaiFileContentPreviewOpenArguments, generation: number, signal: AbortSignal): Promise<void> {
        const content = await this.#fetchText(inputArguments.previewUrl, signal);
        if (!this.#isCurrent(inputArguments, generation, signal)) {
            return;
        }
        requireContentPreviewModalService().open(
            createTextContentPreviewRequest({
                scope: 'chat',
                type: 'text',
                headerDescription: resolveChatPreviewHeaderDescription('text', inputArguments.contentType),
                baseline: { title: inputArguments.title, content, promptColor: null },
                editable: false,
                languageMode: 'default',
                disableCopyWhenEmpty: true,
                disableDownloadWhenEmpty: true,
                colorToolkit: null,
                sourceReference: null,
                onRequestSave: null,
                onRequestDownload: () => triggerDownloadLink({ href: inputArguments.downloadUrl, filename: inputArguments.title, revokeObjectUrl: false }),
                onRequestCopy: async (text) => await copyChatMessageTextWithFeedback(this.#copyFeedback, text),
                onRequestAttach: null,
                enhance: null,
                openSourceUrl: inputArguments.downloadUrl,
                externalOpenBehavior: 'neverConfirm',
                onStatePotentiallyChanged: null
            })
        );
    }

    #isCurrent(inputArguments: ChatSoaiFileContentPreviewOpenArguments, generation: number, signal: AbortSignal): boolean {
        return !signal.aborted && this.#generation === generation && inputArguments.isCurrent();
    }
}

export { ChatSoaiFileContentPreview };
export type { ChatSoaiFileContentPreviewOpenArguments, SoaiFilePreviewType };
