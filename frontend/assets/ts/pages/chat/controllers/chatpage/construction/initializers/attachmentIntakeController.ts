/* SoAI - Chat attachment intake ownership and lazy conversation acceptance [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/attachmentIntakeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { captureSoaiLinkWorkspaceSnapshot, matchesSoaiLinkWorkspaceSnapshot, normalizeConversationId, type ChatAttachmentIntake } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';

const captureChatAttachmentIntake = (page: ChatControllerInitializationContext): ChatAttachmentIntake => {
    const manager = page.runtime.composerSurface.requireAttachments();
    const draft = page.sessions.composer.draftManager();
    if (draft === null) throw new Error('Attachment intake requires composer draft ownership');
    const ownership = draft.captureSurfaceSnapshot();
    const ownsDraft = (adoptedId?: string): boolean => draft.matchesSurfaceSnapshot(ownership, adoptedId, { content: 'allow-changes' });
    const signal = page.page.pageLifecycle.signal();
    let conversation = page.sessions.conversationView.current();
    let workspace = captureSoaiLinkWorkspaceSnapshot(conversation);
    let adoptedConversationId: string | undefined;
    let acceptance: Promise<string | null> | null = null;
    const isCurrent = (): boolean => signal?.aborted !== true && page.runtime.composerSurface.optionalAttachments() === manager && page.sessions.composer.draftManager() === draft && ownsDraft(adoptedConversationId) && page.sessions.conversationView.current() === conversation && (conversation === null || matchesSoaiLinkWorkspaceSnapshot(conversation, workspace));
    const accept = async (): Promise<string | null> => {
        if (!isCurrent()) return null;
        if (conversation === null) {
            const created = await page.sessions.conversationView.requireActions().createConversation({ transferMode: 'adopt-current' });
            if (created === null) return null;
            adoptedConversationId = created.id;
            if (signal?.aborted || !ownsDraft(adoptedConversationId) || page.sessions.conversationView.current() !== created || page.runtime.composerSurface.optionalAttachments() !== manager) return null;
            conversation = created;
            workspace = captureSoaiLinkWorkspaceSnapshot(created);
        }
        if (!isCurrent()) return null;
        await page.runtime.conversationRuntime.requireConversation().ensureConversationPersisted(conversation);
        if (!isCurrent()) return null;
        const conversationId = normalizeConversationId(conversation.id);
        if (!conversationId) throw new Error('Attachment upload requires a valid conversation id');
        return conversationId;
    };
    return {
        scope: { signal, isCurrent },
        acceptConversation: () => {
            acceptance ??= accept();
            return acceptance;
        }
    };
};

export { captureChatAttachmentIntake };
