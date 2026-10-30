/* SoAI - DOM reconciliation for chat conversation message lists [frontend/assets/ts/pages/chat/controllers/page/renderer/ConversationMessageDomReconcileController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { applyChatMessageDeletedExitAnimation, applyConversationEntryMutation, type ChatPostRenderRequestType, type ConversationRenderEntry } from '@features/chat/public.ts';
import type { ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { decideConversationEntryDomRefresh, shouldAnimateInsertedConversationEntry, type ConversationEntryRefreshDecision } from '@pages/chat/controllers/page/renderer/conversationEntryRefreshController.ts';
import { setConversationRenderCacheSignature } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';
import { resolveMigratedMessageNode } from '@pages/chat/controllers/page/renderer/identitymigration/service.ts';
type PreparedConversationEntry = { markup: TrustedHtml; replacement?: HTMLElement | undefined };
type ExistingMessageNodes = { byId: Map<string, HTMLElement>; idsInOrder: string[]; entriesInOrder: HTMLElement[]; duplicateNodes: HTMLElement[]; unkeyedNodes: HTMLElement[]; hasUnstableEntries: boolean };
type ConversationEntryRefresh = { entry: ConversationRenderEntry; node: HTMLElement; nextSignature: string; decision: Exclude<ConversationEntryRefreshDecision, 'skip'> };

const isConversationEntryRoot = (node: Element): node is HTMLElement => {
    return node instanceof HTMLElement && (node.classList.contains('chat-message') || node.classList.contains('chat-comparison-turn'));
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

    static reconcileConversationDom(inputArguments: { container: Element; renderEntries: ConversationRenderEntry[]; renderSignatureByDomId: ReadonlyMap<string, string>; expectedDomIds: ReadonlySet<string>; existing: ExistingMessageNodes; cache: ConversationRenderCache; isCurrentStreaming: boolean; preparedEntriesByDomId: ReadonlyMap<string, PreparedConversationEntry> }): { postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[]; removedIds: string[]; finalNodesByDomId: Map<string, HTMLElement> } {
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
                const prepared = inputArguments.preparedEntriesByDomId.get(domId);
                if (prepared === undefined) throw new Error(`Prepared conversation markup missing for ${domId}`);
                const insertion = applyConversationEntryMutation({
                    intent: 'insert',
                    documentRef,
                    nextMarkup: prepared.markup,
                    replacement: prepared.replacement,
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

    static refreshMessageMarkupIfNeeded(inputArguments: { refreshes: readonly ConversationEntryRefresh[]; cache: ConversationRenderCache; isCurrentStreaming: boolean; preparedEntriesByDomId: ReadonlyMap<string, PreparedConversationEntry> }): { root: HTMLElement; type: ChatPostRenderRequestType }[] {
        const postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[] = [];
        for (const refresh of inputArguments.refreshes) {
            const { entry, node, nextSignature, decision } = refresh;
            const domId = entry.domId;
            const prepared = inputArguments.preparedEntriesByDomId.get(domId);
            if (prepared === undefined) throw new Error(`Prepared conversation markup missing for ${domId}`);
            if (decision === 'skip-dom-streaming') {
                if (entry.type !== 'message') {
                    throw new Error('Streaming conversation entry refresh requires a message render entry.');
                }
                const mutation = applyConversationEntryMutation({
                    intent: 'streamUpdate',
                    existingRoot: node,
                    entry,
                    nextMarkup: prepared.markup,
                    viewportStabilityScope: 'caller'
                });
                postRenderRequests.push(...mutation.postRenderRequests);
                setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
                continue;
            }
            if (node.classList.contains('chat-comparison-turn')) {
                if (entry.type !== 'comparisonTurn') {
                    throw new Error('Comparison turn refresh requires a comparison render entry.');
                }
                const mutation = applyConversationEntryMutation({
                    intent: 'comparisonUpdate',
                    existingRoot: node,
                    nextMarkup: prepared.markup,
                    isCurrentStreaming: inputArguments.isCurrentStreaming,
                    entry,
                    viewportStabilityScope: 'caller'
                });
                postRenderRequests.push(...mutation.postRenderRequests);
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
                        nextMarkup: prepared.markup,
                        entry,
                        assistantRenderIntent: entry.isActiveStreamingEntry ? 'runningUpdate' : 'idleRefresh',
                        viewportStabilityScope: 'caller'
                    });
                    postRenderRequests.push(...mutation.postRenderRequests);
                    setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
                    continue;
                }
            }
            const mutation = applyConversationEntryMutation({
                intent: 'replace',
                replacement: prepared.replacement,
                existingRoot: node,
                nextMarkup: prepared.markup,
                messageDomId: domId
            });
            postRenderRequests.push(...mutation.postRenderRequests);
            setConversationRenderCacheSignature({ cache: inputArguments.cache, domId, signature: nextSignature });
        }
        return postRenderRequests;
    }
}

export { ConversationMessageDomReconcileController };
export { decideConversationEntryDomRefresh };

export type { PreparedConversationEntry };
