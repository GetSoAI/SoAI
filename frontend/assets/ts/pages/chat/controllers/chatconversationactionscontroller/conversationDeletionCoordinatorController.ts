/* SoAI - Chat conversation delete coordination state [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/conversationDeletionCoordinatorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';

const pendingLocalDeletesByRuntime = new WeakMap<ChatConversationActionsControllerRuntime, Set<string>>();

const resolvePendingLocalDeletes = (runtime: ChatConversationActionsControllerRuntime): Set<string> => {
    const existing = pendingLocalDeletesByRuntime.get(runtime);
    if (existing) {
        return existing;
    }
    const pending = new Set<string>();
    pendingLocalDeletesByRuntime.set(runtime, pending);
    return pending;
};

const markLocalConversationDeletes = (runtime: ChatConversationActionsControllerRuntime, conversationIds: readonly string[]): void => {
    const pending = resolvePendingLocalDeletes(runtime);
    for (const conversationId of conversationIds) {
        pending.add(conversationId);
    }
};

const clearLocalConversationDeletes = (runtime: ChatConversationActionsControllerRuntime, conversationIds: readonly string[]): void => {
    const pending = resolvePendingLocalDeletes(runtime);
    for (const conversationId of conversationIds) {
        pending.delete(conversationId);
    }
};

const isLocalConversationDeletePending = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): boolean => {
    return resolvePendingLocalDeletes(runtime).has(conversationId);
};

export { clearLocalConversationDeletes, isLocalConversationDeletePending, markLocalConversationDeletes };
