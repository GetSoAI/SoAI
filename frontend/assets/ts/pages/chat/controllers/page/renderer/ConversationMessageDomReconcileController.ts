/* SoAI - DOM reconciliation for chat conversation message lists [frontend/assets/ts/pages/chat/controllers/page/renderer/ConversationMessageDomReconcileController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { applyChatMessageDeletedExitAnimation, applyConversationEntryMutation, type ChatPostRenderRequestType, type ConversationRenderEntry } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies, ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { renderConversationEntryMarkup } from '@pages/chat/controllers/page/renderer/conversationEntryRendererController.ts';
import { decideConversationEntryDomRefresh, shouldAnimateInsertedConversationEntry, type ConversationEntryRefreshDecision } from '@pages/chat/controllers/page/renderer/conversationEntryRefreshController.ts';
import { setConversationRenderCacheSignature } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';
import { resolveMigratedMessageNode } from '@pages/chat/controllers/page/renderer/identitymigration/service.ts';
type ExistingMessageNodes = { byId: Map<string, HTMLElement>; idsInOrder: string[]; entriesInOrder: HTMLElement[]; duplicateNodes: HTMLElement[]; unkeyedNodes: HTMLElement[]; hasUnstableEntries: boolean };
type ConversationEntryRefresh = { entry: ConversationRenderEntry; node: HTMLElement; nextSignature: string; decision: Exclude<ConversationEntryRefreshDecision, 'skip'> };

const isConversationEntryRoot = (node: Element): node is HTMLElement => {
    return node instanceof HTMLElement && (node.classList.contains('chat-message') || node.classList.contains('chat-comparison-turn'));
};

const applyPostRenderRequests = (host: ChatCurrentConversationRenderDependencies, requests: { root: HTMLElement; type: ChatPostRenderRequestType }[]): void => {
    for (const request of requests) {
        host.conversationRuntime.requireMessages().postRenderRequest(request.root, request.type);
    }
};

class ConversationMessageDomReconcileController {
    static resolveExistingMessageNodes(container: Element): ExistingMessageNodes {
        const nodes = dom.resolveAll(':scope > .chat-message, :scope > .chat-comparison-turn', container).filter((node): node is HTMLElement => isConversationEntryRoot(node));
        const byId = new Map<string, HTMLElement>();
        const idsInOrder: string[] = [];
        const duplicateNodes: HTMLElement[] = [];
        const unkeyedNodes: HTMLElement[] = [];
        for (const node of nodes) {
            const id = node.getAttribute('data-id');
            if (!id) {
                unkeyedNodes.push(node);
                continue;
            }
            if (byId.has(id)) {
                duplicateNodes.push(node);
            } else {
                byId.set(id, node);
            }
            idsInOrder.push(id);
        }
        return { byId, idsInOrder, entriesInOrder: nodes, duplicateNodes, unkeyedNodes, hasUnstableEntries: duplicateNodes.length > 0 || unkeyedNodes.length > 0 };
    }

    static reconcileConversationDom(inputArguments: { host: ChatCurrentConversationRenderDependencies; container: Element; renderEntries: ConversationRenderEntry[]; renderSignatureByDomId: ReadonlyMap<string, string>; expectedDomIds: ReadonlySet<string>; existing: ExistingMessageNodes; cache: ConversationRenderCache; isCurrentStreaming: boolean }): { postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[]; removedIds: string[]; finalNodesByDomId: Map<string, HTMLElement> } {
        const documentRef = inputArguments.container.ownerDocument;
        const existing = inputArguments.existing;
        const postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[] = [];
        const removedIds: string[] = [];
        const finalNodesByDomId = new Map<string, HTMLElement>();
        let anchor: ChildNode | null = existing.entriesInOrder[0] ?? null;
        const remaining = new Map(existing.byId);
        for (let index = 0; index < inputArguments.renderEntries.length; index += 1) {
            const entry = inputArguments.renderEntries[index];
            if (!entry) {
                continue;
            }
            const domId = entry.domId;
            if (!domId) {
                continue;
            }
            let node = remaining.get(domId) ?? null;
            if (!node) {
                const migrated = resolveMigratedMessageNode({
                    entry,
                    expectedDomId: domId,
                    existingIdsInOrder: existing.idsInOrder,
                    remaining,
                    position: index,
                    cache: inputArguments.cache,
                    expectedDomIds: inputArguments.expectedDomIds
                });
                if (migrated) {
                    node = migrated.node;
                    remaining.delete(migrated.previousDomId);
                }
            }
            if (!node) {
                const markup = renderConversationEntryMarkup(inputArguments.host, entry);
                const insertion = applyConversationEntryMutation({
                    intent: 'insert',
                    documentRef,
                    nextMarkup: markup,
                    messageDomId: domId,
                    animate: shouldAnimateInsertedConversationEntry(inputArguments.isCurrentStreaming)
                });
                const created = insertion.root;
                const signature = inputArguments.renderSignatureByDomId.get(domId) ?? null;
                if (signature === null) {
                    throw new Error(`Conversation message render signature missing for inserted ${domId}`);
                }
                setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature });
                postRenderRequests.push(...insertion.postRenderRequests);
                node = created;
            }
            finalNodesByDomId.set(domId, node);
            if (anchor !== node) {
                inputArguments.container.insertBefore(node, anchor);
            } else {
                anchor = node.nextSibling;
            }
            remaining.delete(domId);
        }
        if (remaining.size > 0) {
            remaining.forEach((node, domId) => {
                removedIds.push(domId);
                if (inputArguments.isCurrentStreaming) {
                    node.remove();
                    return;
                }

                if (dom.resolve('.message-content--deleted', node) === null) {
                    node.remove();
                    return;
                }

                const applied = applyChatMessageDeletedExitAnimation(node, () => {
                    node.remove();
                });
                if (!applied) {
                    node.remove();
                }
            });
        }
        const finalNodes = new Set(finalNodesByDomId.values());
        const unstableNodes = [...existing.duplicateNodes, ...existing.unkeyedNodes];
        for (const unstableNode of unstableNodes) {
            if (unstableNode.parentNode === inputArguments.container && !finalNodes.has(unstableNode)) {
                unstableNode.remove();
            }
        }
        return { postRenderRequests, removedIds, finalNodesByDomId };
    }

    static resolveEntryRefreshes(inputArguments: { renderEntries: ConversationRenderEntry[]; cache: ConversationRenderCache; nodesByDomId: ReadonlyMap<string, HTMLElement>; renderSignatureByDomId: ReadonlyMap<string, string>; isCurrentStreaming: boolean }): ConversationEntryRefresh[] {
        const refreshes: ConversationEntryRefresh[] = [];
        for (const entry of inputArguments.renderEntries) {
            const domId = entry.domId;
            if (!domId) {
                continue;
            }
            const node = inputArguments.nodesByDomId.get(domId);
            if (!node) {
                continue;
            }
            const nextSignature = inputArguments.renderSignatureByDomId.get(domId) ?? null;
            if (nextSignature === null) {
                throw new Error(`Conversation message render signature missing for ${domId}`);
            }
            const previousSignature = inputArguments.cache.renderSignatureByDomId.get(domId) ?? null;
            const decision = decideConversationEntryDomRefresh({
                previousSignature,
                nextSignature,
                isCurrentStreaming: inputArguments.isCurrentStreaming,
                isActiveStreamingMessageEntry: entry.type === 'message' && entry.isActiveStreamingEntry,
                node
            });
            if (decision === 'skip') {
                continue;
            }
            refreshes.push({ entry, node, nextSignature, decision });
        }
        return refreshes;
    }

    static refreshMessageMarkupIfNeeded(inputArguments: { host: ChatCurrentConversationRenderDependencies; refreshes: readonly ConversationEntryRefresh[]; cache: ConversationRenderCache; isCurrentStreaming: boolean }): void {
        for (const refresh of inputArguments.refreshes) {
            const { entry, node, nextSignature, decision } = refresh;
            const domId = entry.domId;
            if (decision === 'skip-dom-streaming') {
                if (entry.type !== 'message') {
                    throw new Error('Streaming conversation entry refresh requires a message render entry.');
                }
                const nextMarkup = renderConversationEntryMarkup(inputArguments.host, entry);
                const mutation = applyConversationEntryMutation({
                    intent: 'streamUpdate',
                    existingRoot: node,
                    entry,
                    nextMarkup,
                    viewportStabilityScope: 'caller'
                });
                applyPostRenderRequests(inputArguments.host, mutation.postRenderRequests);
                setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
                continue;
            }
            const nextMarkup = renderConversationEntryMarkup(inputArguments.host, entry);
            if (node.classList.contains('chat-comparison-turn')) {
                if (entry.type !== 'comparisonTurn') {
                    throw new Error('Comparison turn refresh requires a comparison render entry.');
                }
                const mutation = applyConversationEntryMutation({
                    intent: 'comparisonUpdate',
                    existingRoot: node,
                    nextMarkup,
                    isCurrentStreaming: inputArguments.isCurrentStreaming,
                    entry,
                    viewportStabilityScope: 'caller'
                });
                applyPostRenderRequests(inputArguments.host, mutation.postRenderRequests);
                setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
                continue;
            }
            if (node.classList.contains('assistant')) {
                if (dom.resolve('.message-content--deleted', node) === null) {
                    if (entry.type !== 'message') {
                        throw new Error('Assistant conversation refresh requires a message render entry.');
                    }
                    const mutation = applyConversationEntryMutation({
                        intent: 'refresh',
                        existingRoot: node,
                        nextMarkup,
                        entry,
                        assistantRenderIntent: entry.isActiveStreamingEntry ? 'runningUpdate' : 'idleRefresh',
                        viewportStabilityScope: 'caller'
                    });
                    applyPostRenderRequests(inputArguments.host, mutation.postRenderRequests);
                    setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
                    continue;
                }
            }
            const mutation = applyConversationEntryMutation({
                intent: 'replace',
                existingRoot: node,
                nextMarkup,
                messageDomId: domId
            });
            applyPostRenderRequests(inputArguments.host, mutation.postRenderRequests);
            setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
        }
    }
}

export { ConversationMessageDomReconcileController };
export { decideConversationEntryDomRefresh };
