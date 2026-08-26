/* SoAI - Chat attach modal workspace browse operations [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseWorkspaceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { buildSoaiPathToken } from '@core/soailinks/codec.ts';
import { createDocumentContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { showUserError } from '@core/ui/notifications/notifications.ts';
import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveRecords, resolveSoaiPathDraftRecordTitle, type SoaiPathDraftRecord } from '@features/chat/public.ts';
import type { ChatAttachBrowseWorkspaceHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { abortTrackedBrowseAbortControllers, createTrackedBrowseAbortController, releaseTrackedBrowseAbortController, type BrowseAbortControllerRegistry } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseAbortController.ts';
import type { ChatAttachBrowseResult } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';

type WorkspaceBrowseResult = Extract<ChatAttachBrowseResult, { type: 'workspace' }>;
type BrowseActionGuard = () => boolean;

const copyPreviewText = async (host: ChatAttachBrowseWorkspaceHost, text: string): Promise<void> => {
    await copyTextWithHostClipboardFeedback(
        {
            copyToClipboard: (value, options) => host.presentation.copyToClipboard(value, options),
            hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
            showNotification: (message, type, duration) => host.shared.feedback.show(message, type, duration)
        },
        {
            text,
            successMessage: i18n.t('chat.message.copied'),
            errorMessage: i18n.t('chat.message.copyFailed'),
            unavailableMessage: i18n.t('chat.message.copyFailed'),
            unavailableType: 'error'
        }
    );
};

class ChatAttachBrowseWorkspaceOperations {
    readonly #host: ChatAttachBrowseWorkspaceHost;
    readonly #signal: AbortSignal;
    readonly #controllers: BrowseAbortControllerRegistry = new Set();

    constructor(host: ChatAttachBrowseWorkspaceHost, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
    }

    async preview(result: WorkspaceBrowseResult, isCurrent: BrowseActionGuard): Promise<void> {
        if (!isCurrent()) {
            return;
        }
        const controller = createTrackedBrowseAbortController(this.#controllers, this.#signal);
        try {
            const record = await this.#resolveRecord(result, controller.signal);
            if (record === null || controller.signal.aborted || !isCurrent()) {
                return;
            }
            const contentPart = record.contentPart;
            const rootFingerprint = contentPart.workspaceScope.rootFingerprint;
            const value = contentPart.sourceReference.value;
            const conversationId = this.#conversationId();
            if (conversationId === null || !isCurrent()) {
                return;
            }
            if (result.entryType === 'folder') {
                await this.#openFolderPreview(result, record, conversationId, rootFingerprint, value, controller.signal, isCurrent);
                return;
            }
            if (!isCurrent()) {
                return;
            }
            requireContentPreviewModalService().open(
                createDocumentContentPreviewRequest({
                    scope: 'chat',
                    type: 'document',
                    headerDescription: result.chip,
                    title: resolveSoaiPathDraftRecordTitle(record),
                    sourceReference: { type: 'conversation_soai_path', conversationId, rootFingerprint, value },
                    onRequestDownload: null,
                    onRequestAttach: async () => {
                        await this.attach(result, isCurrent);
                    },
                    openSourceUrl: null,
                    externalOpenBehavior: 'neverConfirm'
                })
            );
        } catch (error) {
            if (controller.signal.aborted) {
                return;
            }
            throw ensureError(error);
        } finally {
            releaseTrackedBrowseAbortController(this.#controllers, controller);
        }
    }

    async attach(result: WorkspaceBrowseResult, isCurrent: BrowseActionGuard): Promise<boolean> {
        if (!isCurrent()) {
            return false;
        }
        const controller = createTrackedBrowseAbortController(this.#controllers, this.#signal);
        try {
            const record = await this.#resolveRecord(result, controller.signal);
            if (record === null || controller.signal.aborted || !isCurrent()) {
                return false;
            }
            const addedCount = this.#host.attachments.addSoaiPaths([record]);
            if (addedCount > 0) {
                this.#host.shared.feedback.show(i18n.plural('chat.attachments.soaiPathLinkAdded', addedCount, { count: addedCount }), 'success');
            }
            return true;
        } catch (error) {
            if (controller.signal.aborted) {
                return false;
            }
            throw ensureError(error);
        } finally {
            releaseTrackedBrowseAbortController(this.#controllers, controller);
        }
    }

    abortPending(): void {
        abortTrackedBrowseAbortControllers(this.#controllers);
    }

    #conversationId(): string | null {
        return toTrimmedStringOrNull(this.#host.conversation.currentId());
    }

    async #resolveRecord(result: WorkspaceBrowseResult, signal: AbortSignal): Promise<SoaiPathDraftRecord | null> {
        const conversation = this.#host.conversation.current();
        const conversationId = toTrimmedStringOrNull(conversation?.id);
        if (conversationId === null) {
            showUserError(i18n.t('chat.attachModal.browseNeedsConversation'));
            throw new Error('Browse attach requires an active conversation');
        }
        const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(conversation);
        const token = buildSoaiPathToken({ virtualPath: result.path, label: result.title });
        const response = await this.#host.shared.api.webui.chat.soaiLinks.resolve(conversationId, { rawText: token }, { signal });
        if (signal.aborted || !matchesSoaiLinkWorkspaceSnapshot(this.#host.conversation.current(), workspaceSnapshot)) {
            return null;
        }
        const records = requireMatchingResolveRecords(response, token);
        const first = records[0];
        if (first === undefined) {
            throw new Error('SoAI link resolve response did not include a record');
        }
        return first;
    }

    async #openFolderPreview(result: WorkspaceBrowseResult, record: SoaiPathDraftRecord, conversationId: string, rootFingerprint: string, value: string, signal: AbortSignal, isCurrent: BrowseActionGuard): Promise<void> {
        const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(this.#host.conversation.current());
        const preview = await this.#host.shared.api.webui.chat.soaiPaths.preview(conversationId, { contentPart: record.contentPart }, { signal });
        if (signal.aborted || !isCurrent() || !matchesSoaiLinkWorkspaceSnapshot(this.#host.conversation.current(), workspaceSnapshot)) {
            return;
        }
        const lines = preview.state === 'available' && preview.entries !== undefined ? preview.entries.map((entry) => entry.name) : [];
        requireContentPreviewModalService().open(
            createTextContentPreviewRequest({
                scope: 'chat',
                type: 'text',
                headerDescription: i18n.t('chat.attachModal.browseChipLiveFolder'),
                baseline: { title: resolveSoaiPathDraftRecordTitle(record), content: lines.join('\n'), promptColor: null },
                editable: false,
                languageMode: 'default',
                disableCopyWhenEmpty: true,
                disableDownloadWhenEmpty: true,
                colorToolkit: null,
                onRequestSave: null,
                onRequestDownload: null,
                onRequestCopy: async (text) => await copyPreviewText(this.#host, text),
                onRequestAttach: async () => {
                    await this.attach(result, isCurrent);
                },
                enhance: null,
                openSourceUrl: null,
                onStatePotentiallyChanged: null,
                sourceReference: { type: 'conversation_soai_path', conversationId, rootFingerprint, value },
                externalOpenBehavior: 'neverConfirm'
            })
        );
    }
}

export { ChatAttachBrowseWorkspaceOperations };
