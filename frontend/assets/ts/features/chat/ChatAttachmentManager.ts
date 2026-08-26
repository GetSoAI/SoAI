/* SoAI - Chat feature attachment manager [frontend/assets/ts/features/chat/ChatAttachmentManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import type { ConversationAttachmentChangedEvent } from '@core/realtime/eventcontracts/attachmentContracts.ts';
import { isArray } from '@core/typeGuards.ts';
import type { ChatAttachment } from '@features/chat/ChatTypes.ts';
import { buildChatAttachmentContentFragmentsFromAttachments, type ContentFragment } from '@features/chat/attachments/attachmentContentFragments.ts';
import { ChatAttachmentCreation } from '@features/chat/attachments/attachmentCreation.ts';
import type { ChatAttachmentManagerOptions } from '@features/chat/attachments/attachmentManagerContracts.ts';
import { applyPhysicalAttachmentChangedEvent, deleteStagedPhysicalAttachment } from '@features/chat/attachments/attachmentPhysicalLifecycle.ts';
import { ChatAttachmentProcessingQueue } from '@features/chat/attachments/attachmentProcessingQueue.ts';
import { handleChatAttachmentUploadPipeline, type AttachmentUploadSource } from '@features/chat/attachments/attachmentUploadPipeline.ts';
import { addResolvedSoaiPathAttachments, discardSoaiPathDraftAttachments, loadSoaiPathAttachmentPreviews } from '@features/chat/attachments/soaiPathDraftAttachmentCollection.ts';
import { isSoaiPathDraftRecord, type SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import { SoaiPathImagePreviewLifecycle } from '@features/chat/attachments/soaiPathImagePreviewLifecycle.ts';

class ChatAttachmentManager {
    #uiManager: ChatAttachmentManagerOptions['uiManager'];
    #logger: ChatAttachmentManagerOptions['logger'];
    #errorHandler: ChatAttachmentManagerOptions['errorHandler'];
    #deletePhysicalAttachment: ((conversationId: string, attachmentId: string) => Promise<void>) | null;
    #unsubscribeAttachmentChanged: (() => void) | null;
    #attachmentCreation: ChatAttachmentCreation;
    #processingQueue: ChatAttachmentProcessingQueue;
    #soaiPathImagePreviewLifecycle: SoaiPathImagePreviewLifecycle;
    #files: ChatAttachment[];
    #draftRevision: number;
    #draftCommitEpoch: number;
    #draftChangeNotifier: ChangeNotificationSource;
    #syncUiAfterAttachmentsChanged(): void {
        this.#uiManager.updateAttachmentsPreview();
        this.#uiManager.updateInputState();
        this.#draftChangeNotifier.notify();
    }

    constructor({ attachmentProcessor, uiManager, logger, errorHandler, deletePhysicalAttachment, subscribeAttachmentChanged, loadSoaiPathImagePreview }: ChatAttachmentManagerOptions) {
        if (!attachmentProcessor) {
            throw new Error('ChatAttachmentManager requires an attachment processor');
        }
        if (!uiManager) {
            throw new Error('ChatAttachmentManager requires a UI manager');
        }
        if (!logger) {
            throw new Error('ChatAttachmentManager requires a logger');
        }
        if (!errorHandler) {
            throw new Error('ChatAttachmentManager requires an error handler');
        }
        this.#uiManager = uiManager;
        this.#logger = logger;
        this.#errorHandler = errorHandler;
        this.#deletePhysicalAttachment = deletePhysicalAttachment === undefined ? null : deletePhysicalAttachment;
        this.#unsubscribeAttachmentChanged = subscribeAttachmentChanged ? subscribeAttachmentChanged((event) => this.#applyPhysicalAttachmentEvent(event)) : null;
        this.#attachmentCreation = new ChatAttachmentCreation({ errorHandler });
        this.#processingQueue = new ChatAttachmentProcessingQueue({
            attachmentProcessor,
            logger,
            errorHandler,
            onAttachmentChanged: () => this.#syncUiAfterAttachmentsChanged()
        });
        this.#soaiPathImagePreviewLifecycle = new SoaiPathImagePreviewLifecycle({
            logger,
            loadPreview: loadSoaiPathImagePreview === undefined ? null : loadSoaiPathImagePreview
        });
        this.#files = [];
        this.#draftRevision = 0;
        this.#draftCommitEpoch = 0;
        this.#draftChangeNotifier = new ChangeNotificationSource();
    }

    #bumpDraftRevision(): void {
        this.#draftRevision += 1;
    }

    getAttachments(): ChatAttachment[] {
        return [...this.#files];
    }

    getDraftRevision(): number {
        return this.#draftRevision;
    }

    getDraftCommitEpoch(): number {
        return this.#draftCommitEpoch;
    }

    markDraftCommitStarted(): void {
        this.#draftCommitEpoch += 1;
    }

    subscribeDraftChanges(listener: () => void): () => void {
        return this.#draftChangeNotifier.subscribe(listener);
    }

    markKnowledgeAttachmentChanged(): void {
        this.#bumpDraftRevision();
        this.#draftChangeNotifier.notify();
    }

    hasPendingAttachmentProcessing(): boolean {
        return this.#files.some((file) => file.parseStatus === 'processing');
    }

    async waitForAttachments(attachments?: readonly ChatAttachment[]): Promise<void> {
        const list = attachments ?? this.#files;
        if (list.length === 0) {
            return;
        }
        await this.#processingQueue.waitForAttachments(list);
    }

    buildContentFragmentsFromAttachments(attachments: ChatAttachment[]): ContentFragment[] {
        return buildChatAttachmentContentFragmentsFromAttachments(attachments);
    }

    applyPhysicalAttachmentEvent(event: ConversationAttachmentChangedEvent): void {
        this.#applyPhysicalAttachmentEvent(event);
    }

    #applyPhysicalAttachmentEvent(event: ConversationAttachmentChangedEvent): void {
        applyPhysicalAttachmentChangedEvent({
            files: this.#files,
            event,
            errorHandler: this.#errorHandler,
            syncUi: () => {
                this.#bumpDraftRevision();
                this.#syncUiAfterAttachmentsChanged();
            }
        });
    }

    addResolvedSoaiPathRecords(records: readonly SoaiPathDraftRecord[]): number {
        const addedCount = addResolvedSoaiPathAttachments(
            {
                attachments: this.#files,
                imagePreviewLifecycle: this.#soaiPathImagePreviewLifecycle,
                isAttachmentPresent: (attachmentId) => this.#files.some((file) => file.id === attachmentId),
                syncUi: () => this.#syncUiAfterAttachmentsChanged()
            },
            records
        );
        if (addedCount > 0) {
            this.#bumpDraftRevision();
            this.#syncUiAfterAttachmentsChanged();
        }
        return addedCount;
    }

    discardSoaiPathDraftAttachments(materializeRecord: (record: SoaiPathDraftRecord) => void): number {
        const result = discardSoaiPathDraftAttachments(this.#files, this.#soaiPathImagePreviewLifecycle, (attachmentId) => this.#processingQueue.deleteAttachment(attachmentId));
        if (result.removed.length === 0) {
            return 0;
        }
        for (const attachment of result.removed) {
            if (isSoaiPathDraftRecord(attachment.soaiPathRecord)) materializeRecord(attachment.soaiPathRecord);
        }
        this.#files = result.attachments;
        this.#bumpDraftRevision();
        this.#syncUiAfterAttachmentsChanged();
        return result.removed.length;
    }

    checkoutAttachments(attachments?: readonly ChatAttachment[]): ChatAttachment[] {
        this.markDraftCommitStarted();
        if (attachments !== undefined) {
            const attachmentIds = new Set(attachments.map((attachment) => attachment.id));
            const checkedOut = this.#files.filter((attachment) => attachmentIds.has(attachment.id));
            this.#files = this.#files.filter((attachment) => !attachmentIds.has(attachment.id));
            this.#soaiPathImagePreviewLifecycle.releaseAll(checkedOut);
            for (const attachment of checkedOut) {
                this.#processingQueue.deleteAttachment(attachment.id);
            }
            this.#uiManager.updateAttachmentsPreview();
            this.#uiManager.updateInputState();
            if (checkedOut.length > 0) {
                this.#bumpDraftRevision();
                this.#draftChangeNotifier.notify();
            }
            return checkedOut;
        }
        const checkedOut = this.#files;
        this.#files = [];
        this.#soaiPathImagePreviewLifecycle.releaseAll(checkedOut);
        this.#processingQueue.clear();
        this.#uiManager.clearAttachedFiles();
        this.#uiManager.updateInputState();
        if (checkedOut.length > 0) {
            this.#bumpDraftRevision();
            this.#draftChangeNotifier.notify();
        }
        return checkedOut;
    }

    restoreAttachments(attachments: ChatAttachment[]): void {
        const restored = isArray(attachments) ? [...attachments] : [];
        const merged: ChatAttachment[] = [...this.#files];
        const addedAttachments: ChatAttachment[] = [];
        for (const attachment of restored) {
            if (!attachment) {
                continue;
            }
            if (merged.some((existing) => existing.id === attachment.id)) {
                continue;
            }
            merged.push(attachment);
            addedAttachments.push(attachment);
        }
        const changed = addedAttachments.length > 0;
        this.#files = merged;
        if (changed) {
            this.#bumpDraftRevision();
            loadSoaiPathAttachmentPreviews({
                attachments: addedAttachments,
                imagePreviewLifecycle: this.#soaiPathImagePreviewLifecycle,
                isAttachmentPresent: (attachmentId) => this.#files.some((file) => file.id === attachmentId),
                syncUi: () => this.#syncUiAfterAttachmentsChanged()
            });
        }
        this.#uiManager.updateAttachmentsPreview();
        this.#uiManager.updateInputState();
        if (changed) {
            this.#draftChangeNotifier.notify();
        }
    }

    async handleFiles(files: File[], options: { forceDocument?: boolean } = {}): Promise<void> {
        if (!isArray(files) || files.length === 0) {
            return;
        }
        const pendingOperations: Promise<void>[] = [];
        const attachments = await this.#attachmentCreation.createAttachments(files, options);
        for (const attachment of attachments) {
            this.#files.push(attachment);
            this.#bumpDraftRevision();
            this.#syncUiAfterAttachmentsChanged();
            pendingOperations.push(this.#processingQueue.processAttachment(attachment));
        }
        const settledResults = await Promise.allSettled(pendingOperations);
        const failures = settledResults.filter((settledResult): settledResult is PromiseRejectedResult => settledResult.status === 'rejected');
        if (failures.length > 0) {
            this.#logger('warn', `${failures.length} file processing operations failed`, failures);
        }
        this.#syncUiAfterAttachmentsChanged();
    }

    async handleUpload(files: File[], inputArguments: { source: AttachmentUploadSource; visionSupported: boolean }): Promise<void> {
        await handleChatAttachmentUploadPipeline({
            files,
            source: inputArguments.source,
            visionSupported: inputArguments.visionSupported,
            handleFiles: (nextFiles, options) => this.handleFiles(nextFiles, options),
            logger: this.#logger,
            errorHandler: this.#errorHandler
        });
    }

    async removeAttachedFile(fileId: string, materializeRecord: (record: SoaiPathDraftRecord) => void): Promise<void> {
        const removedCandidate = this.#files.find((file) => file.id === fileId);
        const removed = removedCandidate === undefined ? null : removedCandidate;
        const waitForProcessing = removed ? this.#processingQueue.waitForAttachment(removed) : null;
        this.#files = this.#files.filter((fileValue) => fileValue.id !== fileId);
        if (removed) {
            this.#bumpDraftRevision();
            this.#soaiPathImagePreviewLifecycle.release(removed);
            if (isSoaiPathDraftRecord(removed.soaiPathRecord)) materializeRecord(removed.soaiPathRecord);
        }
        this.#processingQueue.deleteAttachment(fileId);
        this.#syncUiAfterAttachmentsChanged();
        if (!removed) {
            return;
        }
        await waitForProcessing;
        await deleteStagedPhysicalAttachment({
            attachment: removed,
            deletePhysicalAttachment: this.#deletePhysicalAttachment,
            logger: this.#logger,
            errorHandler: this.#errorHandler
        });
    }

    dispose(): void {
        this.#processingQueue.clear();
        this.#soaiPathImagePreviewLifecycle.dispose();
        const unsubscribe = this.#unsubscribeAttachmentChanged;
        this.#unsubscribeAttachmentChanged = null;
        if (!unsubscribe) {
            return;
        }
        try {
            unsubscribe?.();
        } catch (error) {
            this.#logger('warn', 'Failed to unsubscribe chat attachment events', ensureError(error));
        }
    }
}

export { ChatAttachmentManager, type ContentFragment };
