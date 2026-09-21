/* SoAI - Chat attach modal SoAI link controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachSoaiLinkController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveRecords } from '@features/chat/public.ts';
import type { ChatAttachSoaiLinkHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { ChatAttachDraftAttachmentListController } from '@pages/chat/controllers/modals/chatattach/ChatAttachDraftAttachmentListController.ts';
import type { ChatAttachSoaiLinkElements } from '@pages/chat/controllers/modals/chatattach/types.ts';
import { resolveSoaiLinkDraftRecordsWithNotification } from '@pages/chat/controllers/soaiLinkResolveController.ts';

class ChatAttachSoaiLinkController {
    readonly #host: ChatAttachSoaiLinkHost;
    readonly #elements: ChatAttachSoaiLinkElements;
    readonly #signal: AbortSignal;
    readonly #draftListController: ChatAttachDraftAttachmentListController;
    #active = false;
    #generation = 0;
    #resolveController: AbortController | null = null;
    readonly #handleInputEvent = (): void => {
        this.#handleInput();
    };
    readonly #handlePasteEvent = (event: ClipboardEvent): void => {
        this.#handlePaste(event);
    };

    constructor(host: ChatAttachSoaiLinkHost, elements: ChatAttachSoaiLinkElements, signal: AbortSignal) {
        this.#host = host;
        this.#elements = elements;
        this.#signal = signal;
        this.#draftListController = new ChatAttachDraftAttachmentListController(host, elements.draftList, signal, 'soaiLink');
        this.#bind();
    }

    activate(): void {
        const wasActive = this.#active;
        this.#active = true;
        this.#draftListController.activate();
        if (!wasActive) {
            this.#handleInput();
        }
    }

    deactivate(): void {
        this.#active = false;
        this.#generation += 1;
        this.#abortResolve();
        this.#draftListController.deactivate();
    }

    #bind(): void {
        this.#elements.input.addEventListener('paste', this.#handlePasteEvent, { signal: this.#signal });
        this.#elements.input.addEventListener('input', this.#handleInputEvent, { signal: this.#signal });
    }

    #handlePaste(event: ClipboardEvent): void {
        const pastedText = event.clipboardData?.getData('text/plain') ?? '';
        if (!containsSoaiPathToken(pastedText)) {
            return;
        }
        event.preventDefault();
        const input = this.#elements.input;
        const nextValue = this.#resolvePastedValue(input, pastedText);
        input.value = nextValue;
        this.#scheduleResolve(nextValue);
    }

    #handleInput(): void {
        const value = this.#elements.input.value;
        if (!containsSoaiPathToken(value)) {
            return;
        }
        this.#scheduleResolve(value);
    }

    #scheduleResolve(value: string): void {
        if (!this.#active) {
            return;
        }
        this.#generation += 1;
        this.#abortResolve();
        this.#host.execution.run('chat:attachModalSoaiLinkResolve', async () => {
            await this.#resolveCurrentValue(value);
        });
    }

    async #resolveCurrentValue(inputValue: string): Promise<void> {
        if (!this.#active || !containsSoaiPathToken(inputValue) || this.#elements.input.value !== inputValue) {
            return;
        }
        this.#abortResolve();
        this.#generation += 1;
        const generation = this.#generation;
        const controller = new AbortController();
        this.#resolveController = controller;
        const conversationId = await this.#resolveConversationId();
        if (conversationId === null || !this.#isCurrentField(generation, controller.signal, inputValue)) {
            this.#releaseController(controller);
            return;
        }
        const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(this.#host.conversation.current());
        if (workspaceSnapshot === null || workspaceSnapshot.conversationId !== conversationId || !this.#isCurrent(generation, controller.signal, inputValue, workspaceSnapshot, null)) {
            this.#releaseController(controller);
            return;
        }
        const draftCommitEpoch = this.#host.attachments.draftCommitEpoch();
        try {
            await runWithAbortSignalScope([this.#signal, controller.signal], async (signal) => {
                const response = await resolveSoaiLinkDraftRecordsWithNotification({
                    api: this.#host.shared.api,
                    conversationId,
                    rawText: inputValue,
                    signal,
                    boundaryName: 'chat:attachModalResolveSoaiLinks'
                });
                if (response === null) {
                    return;
                }
                const records = requireMatchingResolveRecords(response, inputValue);
                if (!this.#isCurrent(generation, signal, inputValue, workspaceSnapshot, draftCommitEpoch)) {
                    return;
                }
                const addedCount = this.#host.attachments.addSoaiPaths(records, 'soaiLink');
                if (!this.#isCurrent(generation, signal, inputValue, workspaceSnapshot, null)) {
                    return;
                }
                this.#elements.input.value = '';
                if (addedCount > 0) {
                    this.#host.shared.feedback.show(i18n.plural('chat.attachments.soaiPathLinkAdded', addedCount, { count: addedCount }), 'success');
                }
            });
        } catch (error) {
            if (controller.signal.aborted || this.#signal.aborted) {
                return;
            }
            throw ensureError(error);
        } finally {
            this.#releaseController(controller);
        }
    }

    async #resolveConversationId(): Promise<string | null> {
        const currentConversation = this.#host.conversation.current();
        const currentConversationId = toTrimmedStringOrNull(currentConversation?.id);
        if (currentConversationId !== null) {
            return currentConversationId;
        }
        const createdConversation = await this.#host.conversation.actions.createConversation({ transferMode: 'adopt-current' });
        return toTrimmedStringOrNull(createdConversation?.id);
    }

    #resolvePastedValue(input: HTMLTextAreaElement, pastedText: string): string {
        const start = input.selectionStart ?? input.value.length;
        const end = input.selectionEnd ?? input.value.length;
        return `${input.value.slice(0, start)}${pastedText}${input.value.slice(end)}`;
    }

    #isCurrent(generation: number, signal: AbortSignal, inputValue: string, workspaceSnapshot: ReturnType<typeof captureSoaiLinkWorkspaceSnapshot> | null, draftCommitEpoch: number | null): boolean {
        if (!this.#isCurrentField(generation, signal, inputValue)) {
            return false;
        }
        if (workspaceSnapshot !== null && !matchesSoaiLinkWorkspaceSnapshot(this.#host.conversation.current(), workspaceSnapshot)) {
            return false;
        }
        if (draftCommitEpoch !== null && this.#host.attachments.draftCommitEpoch() !== draftCommitEpoch) {
            return false;
        }
        return true;
    }

    #isCurrentField(generation: number, signal: AbortSignal, inputValue: string): boolean {
        return this.#active && !this.#signal.aborted && !signal.aborted && this.#generation === generation && this.#elements.input.value === inputValue;
    }

    #abortResolve(): void {
        const controller = this.#resolveController;
        this.#resolveController = null;
        if (controller !== null && !controller.signal.aborted) {
            controller.abort();
        }
    }

    #releaseController(controller: AbortController): void {
        if (this.#resolveController === controller) {
            this.#resolveController = null;
        }
    }
}

export { ChatAttachSoaiLinkController };
