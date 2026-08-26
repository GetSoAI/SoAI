/* SoAI - Message DOM identity migration rules [frontend/assets/ts/pages/chat/controllers/page/renderer/identitymigration/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isIndexedToPersistedMessageDomIdUpgrade, resolveAssistantSemanticIdentityKey, resolveIndexedMessageDomPosition, resolveConversationInputMessageIdentifierFromMessage, resolveMessageDomId, resolvePersistedMessageIdentifier, type ConversationRenderEntry } from '@features/chat/public.ts';
import type { ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { migrateConversationRenderCacheSignature } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';

type ReusedMigratedMessageNode = { node: HTMLElement; previousDomId: string };

const isPersistedDomIdUpgradeCandidate = (inputArguments: { entry: ConversationRenderEntry; expectedDomId: string; existingDomId: string }): boolean => {
    if (inputArguments.entry.type !== 'message') {
        return false;
    }
    if (inputArguments.entry.message.role === 'assistant') {
        return false;
    }
    if (!isIndexedToPersistedMessageDomIdUpgrade(inputArguments.existingDomId, inputArguments.expectedDomId)) {
        return false;
    }
    return resolveIndexedMessageDomPosition(inputArguments.existingDomId) === inputArguments.entry.index;
};

const isPersistedMessageReidentificationCandidate = (inputArguments: { entry: ConversationRenderEntry; expectedDomId: string; existingDomId: string; existingNode: HTMLElement; expectedDomIds: ReadonlySet<string> }): boolean => {
    if (inputArguments.entry.type !== 'message' || inputArguments.entry.message.role === 'assistant') {
        return false;
    }
    if (inputArguments.existingDomId === inputArguments.expectedDomId || inputArguments.expectedDomIds.has(inputArguments.existingDomId)) {
        return false;
    }
    if (resolvePersistedMessageIdentifier(inputArguments.existingDomId) === null || resolvePersistedMessageIdentifier(inputArguments.expectedDomId) === null) {
        return false;
    }
    return inputArguments.existingNode.classList.contains('chat-message') && !inputArguments.existingNode.classList.contains('assistant');
};

const isAssistantSemanticDomIdUpgradeCandidate = (inputArguments: { entry: ConversationRenderEntry; expectedDomId: string; existingDomId: string; existingNode: HTMLElement }): boolean => {
    if (inputArguments.entry.type !== 'message' || inputArguments.entry.message.role !== 'assistant' || inputArguments.existingDomId === inputArguments.expectedDomId) {
        return false;
    }
    const existingSemanticIdentity = inputArguments.existingNode.getAttribute('data-assistant-semantic-id');
    if (!existingSemanticIdentity) {
        return false;
    }
    return existingSemanticIdentity === resolveAssistantSemanticIdentityKey(inputArguments.entry.message, 'Assistant message DOM identity migration');
};

const updateMigratedNodeIdentity = (inputArguments: { node: HTMLElement; previousDomId: string; expectedDomId: string; cache: ConversationRenderCache }): void => {
    inputArguments.node.setAttribute('data-id', inputArguments.expectedDomId);
    migrateConversationRenderCacheSignature({ cache: inputArguments.cache, previousDomId: inputArguments.previousDomId, nextDomId: inputArguments.expectedDomId });
};

const resolveMigratedMessageNode = (inputArguments: { entry: ConversationRenderEntry; expectedDomId: string; existingIdsInOrder: string[]; remaining: ReadonlyMap<string, HTMLElement>; position: number; cache: ConversationRenderCache; expectedDomIds: ReadonlySet<string> }): ReusedMigratedMessageNode | null => {
    if (inputArguments.entry.type === 'message' && inputArguments.entry.message.role !== 'assistant' && resolvePersistedMessageIdentifier(inputArguments.expectedDomId) !== null) {
        const conversationInputId = resolveConversationInputMessageIdentifierFromMessage(inputArguments.entry.message);
        if (conversationInputId !== null) {
            const conversationInputMessage = { ...inputArguments.entry.message };
            delete conversationInputMessage.id;
            const previousDomId = resolveMessageDomId(conversationInputMessage, inputArguments.entry.index);
            const conversationInputNode = inputArguments.remaining.get(previousDomId) ?? null;
            if (conversationInputNode !== null) {
                updateMigratedNodeIdentity({ node: conversationInputNode, previousDomId, expectedDomId: inputArguments.expectedDomId, cache: inputArguments.cache });
                return { node: conversationInputNode, previousDomId };
            }
        }
    }
    const existingDomId = inputArguments.existingIdsInOrder[inputArguments.position] ?? '';
    if (!existingDomId) {
        return null;
    }
    const existingNode = inputArguments.remaining.get(existingDomId) ?? null;
    if (!existingNode) {
        return null;
    }
    if (isAssistantSemanticDomIdUpgradeCandidate({ entry: inputArguments.entry, expectedDomId: inputArguments.expectedDomId, existingDomId, existingNode })) {
        updateMigratedNodeIdentity({ node: existingNode, previousDomId: existingDomId, expectedDomId: inputArguments.expectedDomId, cache: inputArguments.cache });
        return { node: existingNode, previousDomId: existingDomId };
    }
    if (isPersistedMessageReidentificationCandidate({ entry: inputArguments.entry, expectedDomId: inputArguments.expectedDomId, existingDomId, existingNode, expectedDomIds: inputArguments.expectedDomIds })) {
        updateMigratedNodeIdentity({ node: existingNode, previousDomId: existingDomId, expectedDomId: inputArguments.expectedDomId, cache: inputArguments.cache });
        return { node: existingNode, previousDomId: existingDomId };
    }
    if (!isPersistedDomIdUpgradeCandidate({ entry: inputArguments.entry, expectedDomId: inputArguments.expectedDomId, existingDomId })) {
        return null;
    }
    updateMigratedNodeIdentity({ node: existingNode, previousDomId: existingDomId, expectedDomId: inputArguments.expectedDomId, cache: inputArguments.cache });
    return { node: existingNode, previousDomId: existingDomId };
};

export { resolveMigratedMessageNode };
export type { ReusedMigratedMessageNode };
