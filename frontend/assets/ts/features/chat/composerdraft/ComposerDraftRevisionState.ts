/* SoAI - Composer draft revision and conflict state [frontend/assets/ts/features/chat/composerdraft/ComposerDraftRevisionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ComposerDraftManagerDependencies } from '@features/chat/composerdraft/composerDraftTypes.ts';

class ComposerDraftRevisionState {
    readonly #revisionByConversation = new Map<string, number>();
    readonly #conflictWarningConversations = new Set<string>();
    readonly #showNotification: ComposerDraftManagerDependencies['showNotification'];

    constructor(showNotification: ComposerDraftManagerDependencies['showNotification']) {
        this.#showNotification = showNotification;
    }

    get(conversationId: string): number {
        return this.#revisionByConversation.get(conversationId) ?? 0;
    }

    observe(conversationId: string, revision: number): void {
        if (revision > this.get(conversationId)) this.#revisionByConversation.set(conversationId, revision);
    }

    discard(conversationId: string): void {
        this.#revisionByConversation.delete(conversationId);
        this.#conflictWarningConversations.delete(conversationId);
    }

    record(conversationId: string, revision: number, conflicted: boolean): void {
        if (revision > this.get(conversationId)) this.#revisionByConversation.set(conversationId, revision);
        if (!conflicted) {
            this.#conflictWarningConversations.delete(conversationId);
            return;
        }
        if (this.#conflictWarningConversations.has(conversationId)) return;
        this.#conflictWarningConversations.add(conversationId);
        this.#showNotification(i18n.t('chat.draft.conflict'), 'warning');
    }
}

export { ComposerDraftRevisionState };
