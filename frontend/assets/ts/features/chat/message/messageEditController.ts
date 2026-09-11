/* SoAI - Chat feature message edit controller [frontend/assets/ts/features/chat/message/messageEditController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { reportChatStreamTerminalizationFailureOnce } from '@features/chat/chatstreamservice/controller/terminalizationError.ts';
import { runChatExecutionModelPreflightBoundary } from '@features/chat/modelExecutionPreflight.ts';
import { commitChatMessageEdit, commitChatMessageResend } from '@features/chat/message/messageEditCommit.ts';
import { beginMessageTextEditing, restoreRenderedMessageText, setMessageTextEditingBusy } from '@features/chat/message/messageEditDom.ts';
import { handleEditAttachmentClick, resolveRemovedEditAttachmentIndexes } from '@features/chat/message/messageEditAttachmentDom.ts';
import type { ChatMessageEditControllerDependencies } from '@features/chat/message/messageMutationControllerContracts.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { readEditableUserText, userMessageHasNonTextContent } from '@features/chat/message/messageEditing.ts';
import { hasRemainingEditedMessageContent } from '@features/chat/message/messageEditValidity.ts';

class ChatMessageEditController {
    readonly #dependencies: ChatMessageEditControllerDependencies;
    readonly #save: SaveController;

    #activeMessageId: string | null = null;
    #baselineText: string = '';
    #baselineHasNonTextContent: boolean = false;
    #inputAbort: AbortController | null = null;
    readonly #domChangeHandler: EventListener;

    constructor(dependencies: ChatMessageEditControllerDependencies) {
        this.#dependencies = dependencies;
        this.#save = createSaveController({
            headerContextId: 'chat.messageEdit',
            headerPriority: SAVE_HEADER_PRIORITY_PAGE,
            requestContextLabel: 'Chat message edit',
            units: [
                {
                    id: 'chat-message-edit',
                    hasChanges: () => this.#hasChanges(),
                    isValid: () => this.#isValid(),
                    save: async () => await this.#commitSave()
                }
            ]
        });
        this.#save.attach({
            resolveSaveButtons: () => {
                const button = this.#resolveActiveSaveButton();
                return button ? [button] : [];
            },
            onBusyChange: (busy) => {
                const container = this.#resolveActiveContainer();
                if (container) setMessageTextEditingBusy(container, busy);
            }
        });
        this.#domChangeHandler = (): void => this.#save.notifyChanged();
        this.#dependencies.view.domChangeTarget.addEventListener('change', this.#domChangeHandler);
    }

    dispose(): void {
        this.#dependencies.view.domChangeTarget.removeEventListener('change', this.#domChangeHandler);
        this.#abortEditInput();
        this.#save.dispose();
    }

    #isCurrentConversationExecuting(): boolean {
        const conversationId = this.#dependencies.getCurrentConversation()?.id ?? '';
        return conversationId ? this.#dependencies.isConversationExecuting(conversationId) : false;
    }

    beginEditing(message: ChatMessage, messageId: string): void {
        if (this.#save.isSaving() || this.#isCurrentConversationExecuting()) {
            return;
        }
        const normalizedId = normalizeMessageDomId(messageId);
        if (!normalizedId) {
            return;
        }
        if (this.#activeMessageId !== null && this.#activeMessageId !== normalizedId) {
            const conversation = this.#dependencies.getCurrentConversation();
            if (conversation) {
                const prior = this.#dependencies.resolveMessageReference(conversation, this.#activeMessageId);
                if (prior.message) {
                    this.endEditing(prior.message, this.#activeMessageId);
                } else {
                    this.#clearActiveState();
                }
            }
        }

        const container = this.#dependencies.view.resolveMessageContainer(normalizedId);
        if (!container) {
            return;
        }
        const editableText = readEditableUserText(message);
        const removeIcon = this.#dependencies.view.getIcon('close', { size: 12, strokeWidth: 2.2 });
        const textarea = beginMessageTextEditing(container, editableText, removeIcon);
        if (!textarea) {
            return;
        }

        this.#activeMessageId = normalizedId;
        this.#baselineText = toTrimmedString(editableText);
        this.#baselineHasNonTextContent = userMessageHasNonTextContent(message);
        this.#wireEditInput(textarea, container);
        this.#save.notifyChanged();
    }

    endEditing(message: ChatMessage, messageId: string): void {
        const normalizedId = normalizeMessageDomId(messageId);
        if (this.#save.isSaving() || !normalizedId || this.#activeMessageId !== normalizedId) {
            return;
        }
        const container = this.#dependencies.view.resolveMessageContainer(normalizedId);
        if (!container) {
            this.#clearActiveState();
            this.#save.notifyChanged();
            return;
        }
        restoreRenderedMessageText({
            container,
            message,
            renderMessageTextContent: this.#dependencies.view.renderMessageTextContent,
            postRender: this.#dependencies.view.postRender
        });
        this.#clearActiveState();
        this.#save.notifyChanged();
    }

    requestSave(): Promise<void> {
        return this.#save.requestSave();
    }

    async resendMessage(messageId: string): Promise<void> {
        try {
            await this.#dependencies.runWithBoundary('chat:resendMessage', async () => {
                await runChatExecutionModelPreflightBoundary(async () => {
                    await commitChatMessageResend(this.#dependencies, { messageId });
                });
            });
        } catch (error) {
            this.#reportRequestFailure(ensureError(error));
        }
    }

    #reportRequestFailure(error: Error): void {
        if (!reportChatStreamTerminalizationFailureOnce(error, (failure) => this.#dependencies.reportRequestFailure(failure))) {
            this.#dependencies.reportRequestFailure(error);
        }
    }

    notifyChanged(): void {
        if (!this.#activeMessageId) {
            return;
        }
        this.#save.notifyChanged();
    }

    hasChanges(): boolean {
        return this.#hasChanges();
    }

    #hasChanges(): boolean {
        const textarea = this.#resolveActiveTextarea();
        if (!textarea) {
            return false;
        }
        return readTrimmedInputValue(textarea) !== this.#baselineText || this.#resolveRemovedAttachmentIndexes().length > 0;
    }

    isValid(): boolean {
        return this.#isValid();
    }

    #isValid(): boolean {
        if (!this.#hasChanges()) {
            return true;
        }
        if (this.#isCurrentConversationExecuting()) {
            return false;
        }
        const textarea = this.#resolveActiveTextarea();
        if (!textarea) {
            return false;
        }
        return hasRemainingEditedMessageContent(textarea, this.#baselineHasNonTextContent);
    }

    async commitSave(): Promise<void> {
        await this.#commitSave();
    }

    async #commitSave(): Promise<void> {
        const textarea = this.#resolveActiveTextarea();
        const messageId = this.#activeMessageId;
        if (!textarea || !messageId) {
            return;
        }
        const updatedText = readTrimmedInputValue(textarea);
        if (!hasRemainingEditedMessageContent(textarea, this.#baselineHasNonTextContent)) {
            textarea.focus();
            return;
        }
        const removedAttachmentIndexes = this.#resolveRemovedAttachmentIndexes();
        if (updatedText === this.#baselineText && removedAttachmentIndexes.length === 0) {
            return;
        }
        const container = this.#dependencies.view.resolveMessageContainer(messageId);
        if (!container || !container.contains(textarea)) {
            return;
        }
        const committedSignal = createDeferred<void>();
        let editWasCommitted = false;
        const completion = this.#dependencies.runWithBoundary('chat:editMessage', async () => {
            const preflightAccepted = await runChatExecutionModelPreflightBoundary(async () => {
                await commitChatMessageEdit(this.#dependencies, {
                    messageId,
                    updatedText,
                    removedAttachmentIndexes,
                    onSettled: (settlement) => {
                        editWasCommitted = settlement.status === 'committed';
                        try {
                            setMessageTextEditingBusy(container, false);
                            if (settlement.status === 'committed' && settlement.currentMessage !== null) {
                                restoreRenderedMessageText({
                                    container,
                                    message: settlement.currentMessage,
                                    renderMessageTextContent: this.#dependencies.view.renderMessageTextContent,
                                    postRender: this.#dependencies.view.postRender
                                });
                            }
                        } finally {
                            if (this.#activeMessageId === messageId) {
                                this.#clearActiveState();
                                this.#save.notifyChanged();
                            }
                            committedSignal.resolve();
                        }
                    }
                });
            });
            if (!preflightAccepted) {
                return;
            }
        });
        terminateHandledPromise(
            completion.then(
                () => committedSignal.resolve(),
                (error): void => {
                    const runtimeError = ensureError(error);
                    if (!editWasCommitted) {
                        committedSignal.reject(runtimeError);
                        return;
                    }
                    this.#reportRequestFailure(runtimeError);
                }
            )
        );
        await committedSignal.promise;
    }

    #wireEditInput(textarea: HTMLTextAreaElement, container: HTMLElement): void {
        this.#abortEditInput();
        const controller = new AbortController();
        this.#inputAbort = controller;
        const handleEditInput = (): void => this.#save.notifyChanged();
        textarea.addEventListener('input', handleEditInput, { signal: controller.signal });
        const handleEditChange = (): void => this.#save.notifyChanged();
        textarea.addEventListener('change', handleEditChange, { signal: controller.signal });
        const handleAttachmentClick = (event: Event): void => {
            if (handleEditAttachmentClick(container, event)) {
                this.#save.notifyChanged();
            }
        };
        container.addEventListener('click', handleAttachmentClick, { signal: controller.signal });
    }

    #abortEditInput(): void {
        this.#inputAbort?.abort();
        this.#inputAbort = null;
    }

    #clearActiveState(): void {
        this.#abortEditInput();
        this.#activeMessageId = null;
        this.#baselineText = '';
        this.#baselineHasNonTextContent = false;
    }

    #resolveActiveTextarea(): HTMLTextAreaElement | null {
        const container = this.#resolveActiveContainer();
        if (!container) {
            return null;
        }
        const textarea = dom.resolve('.message-edit-input', container);
        return textarea instanceof HTMLTextAreaElement ? textarea : null;
    }

    #resolveRemovedAttachmentIndexes(): number[] {
        const container = this.#resolveActiveContainer();
        if (!container) {
            return [];
        }
        return resolveRemovedEditAttachmentIndexes(container);
    }

    #resolveActiveSaveButton(): HTMLButtonElement | null {
        const container = this.#resolveActiveContainer();
        if (!container) {
            return null;
        }
        const button = dom.resolve('.edit-message-save-btn', container);
        return button instanceof HTMLButtonElement ? button : null;
    }

    #resolveActiveContainer(): HTMLElement | null {
        const messageId = this.#activeMessageId;
        if (!messageId) {
            return null;
        }
        return this.#dependencies.view.resolveMessageContainer(messageId);
    }
}

export { ChatMessageEditController };
export type { ChatMessageEditControllerDependencies };
