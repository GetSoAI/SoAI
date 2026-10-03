/* SoAI - Chat attach modal workspace browse operations [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseWorkspaceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { buildSoaiPathToken } from '@core/soailinks/codec.ts';
import { showUserError } from '@core/ui/notifications/notifications.ts';
import { ChatSoaiPathContentPreview, captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, requireMatchingResolveRecords, resolveSoaiPathDraftRecordTitle, type SoaiPathDraftRecord } from '@features/chat/public.ts';
import type { ChatAttachBrowseWorkspaceHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { abortTrackedBrowseAbortControllers, createTrackedBrowseAbortController, releaseTrackedBrowseAbortController, type BrowseAbortControllerRegistry } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseAbortController.ts';
import type { ChatAttachBrowseResult } from '@pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts';

type WorkspaceBrowseResult = Extract<ChatAttachBrowseResult, { type: 'workspace' }>;
type BrowseActionGuard = () => boolean;

class ChatAttachBrowseWorkspaceOperations {
    readonly #host: ChatAttachBrowseWorkspaceHost;
    readonly #signal: AbortSignal;
    readonly #controllers: BrowseAbortControllerRegistry = new Set();
    readonly #preview: ChatSoaiPathContentPreview;

    constructor(host: ChatAttachBrowseWorkspaceHost, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
        this.#preview = new ChatSoaiPathContentPreview({
            soaiPathsApi: host.shared.api.webui.chat.soaiPaths,
            runWithBoundary: (name, operation) => host.execution.boundary(name, operation),
            hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
            copyToClipboard: (text, options) => host.presentation.copyToClipboard(text, options),
            showNotification: (message, type) => host.shared.feedback.show(message, type)
        });
        signal.addEventListener('abort', this.abortPending, { once: true });
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
            const conversationId = this.#conversationId();
            if (conversationId === null || !isCurrent()) {
                return;
            }
            const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(this.#host.conversation.current());
            this.#preview.open({
                conversationId,
                contentPart,
                title: resolveSoaiPathDraftRecordTitle(record),
                headerDescription: result.chip,
                isCurrent: () => !this.#signal.aborted && isCurrent() && matchesSoaiLinkWorkspaceSnapshot(this.#host.conversation.current(), workspaceSnapshot),
                onRequestAttach: async () => {
                    await this.attach(result, isCurrent);
                }
            });
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
            const addedCount = this.#host.attachments.addSoaiPaths([record], 'browse');
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

    readonly abortPending = (): void => {
        abortTrackedBrowseAbortControllers(this.#controllers);
        this.#preview.reset();
    };

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
}

export { ChatAttachBrowseWorkspaceOperations };
