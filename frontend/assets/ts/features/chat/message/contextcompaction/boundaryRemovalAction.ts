/* SoAI - Context compaction boundary removal message action [frontend/assets/ts/features/chat/message/contextcompaction/boundaryRemovalAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatMessageActionData, ChatMessageActionsDependencies } from '@features/chat/message/actionDeps.ts';
import { resolveToolCallActionIdentity } from '@features/chat/message/toolCallActionIdentity.ts';

const removeCompactionBoundary = async (dependencies: ChatMessageActionsDependencies, conversation: ConversationContract, data: ChatMessageActionData | undefined): Promise<void> => {
    const conversationId = isString(conversation.id) && conversation.id.trim() ? conversation.id.trim() : '';
    const expectedLastModifiedAtMs = typeof conversation.updatedAt === 'number' && Number.isInteger(conversation.updatedAt) && conversation.updatedAt > 0 ? conversation.updatedAt : null;
    const identity = resolveToolCallActionIdentity(data);
    if (!conversationId || expectedLastModifiedAtMs === null || identity === null) {
        dependencies.interaction.showNotification(i18n.t('chat.agent.compact.failed'), 'error');
        return;
    }
    await dependencies.runtime.runConversationExecutionIfIdle(conversationId, async () => {
        await dependencies.runtime.removeCompactionBoundary({
            conversationId,
            assistantTurnAtMs: identity.assistantTurnAtMs,
            modelVariantIndex: identity.modelVariantIndex,
            toolCallId: identity.toolCallId,
            expectedLastModifiedAtMs
        });
        await dependencies.runtime.loadConversationMessages(conversationId, { force: true });
        dependencies.runtime.invalidateChatMarkup('both');
        await dependencies.runtime.renderCurrentConversation();
        await dependencies.runtime.refreshConversationsUI();
    });
};

export { removeCompactionBoundary };
