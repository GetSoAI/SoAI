/* SoAI - Chat page current conversation message controller [frontend/assets/ts/pages/chat/controllers/page/renderer/currentConversationMessageController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { joinUiHtml } from '@core/security/uiHtml.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { applyConversationEntryMutation, resolveConversationEntryElements, resolveConversationRenderEntrySignature, withAssistantViewportStability, type Conversation, type ConversationMessage, type ChatPostRenderRequestType, type ConversationRenderEntry } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies, ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { ConversationMessageDomReconcileController, type PreparedConversationEntry } from '@pages/chat/controllers/page/renderer/ConversationMessageDomReconcileController.ts';
import { renderConversationEntryMarkup } from '@pages/chat/controllers/page/renderer/conversationEntryRendererController.ts';
import { messageWindowLoadingElementsMatch, renderMessageWindowLoadingMarkup, syncMessageWindowLoadingElements } from '@pages/chat/controllers/page/renderer/currentConversationMessageWindowLoadingController.ts';
import { createConversationRenderCache, deleteConversationRenderCacheSignature, getOrCreateConversationRenderCache, replaceConversationRenderCacheIndex } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';

type RenderCurrentConversationMessageStateArguments = {
    host: ChatCurrentConversationRenderDependencies;
    container: Element;
    previousCache: ConversationRenderCache | null;
    conversationKey: string;
    renderEntries: ConversationRenderEntry[];
    isCurrentStreaming: boolean;
    showEarlierMessagesLoading: boolean;
    showNewerMessagesLoading: boolean;
    isCurrent(): boolean;
    history: Conversation['history'];
    viewportStabilityScope: 'transaction' | 'caller';
};

type ConversationPresentationSignatureSnapshot = {
    assistantAvatar: string | null;
    userAvatar: string | null;
};

const resolveMessageSenderLabelCacheSignature = (host: ChatCurrentConversationRenderDependencies, message: ConversationMessage, role: string): string => {
    const label = host.modelSession.messageSenderLabel(message, role);
    return `${String(label.length)}:${label}`;
};

const resolveAvatarValueCacheSignature = (avatarUrl: string | null): string => {
    if (avatarUrl === null) {
        return 'null';
    }
    return `${String(avatarUrl.length)}:${formatHashSignature(avatarUrl)}`;
};

const createConversationPresentationSignatureSnapshot = (): ConversationPresentationSignatureSnapshot => {
    return {
        assistantAvatar: null,
        userAvatar: null
    };
};

const resolveMessageAvatarCacheSignature = (host: ChatCurrentConversationRenderDependencies, snapshot: ConversationPresentationSignatureSnapshot, role: string): string => {
    if (role === 'assistant') {
        snapshot.assistantAvatar ??= resolveAvatarValueCacheSignature(host.presentation.assistantAvatarUrl());
        return `assistant:${snapshot.assistantAvatar}`;
    }
    if (role === 'user') {
        snapshot.userAvatar ??= resolveAvatarValueCacheSignature(host.presentation.userAvatarUrl());
        return `user:${snapshot.userAvatar}`;
    }
    return role;
};

const resolveConversationEntryPresentationCacheSignatures = (host: ChatCurrentConversationRenderDependencies, entry: ConversationRenderEntry, snapshot: ConversationPresentationSignatureSnapshot): { label: string; avatar: string } => {
    if (entry.type === 'message') {
        const role = entry.presentation.normalizedRole;
        return {
            label: resolveMessageSenderLabelCacheSignature(host, entry.message, role),
            avatar: resolveMessageAvatarCacheSignature(host, snapshot, role)
        };
    }
    const labels: string[] = [];
    const avatars: string[] = [];
    for (const variant of entry.variants) {
        if (variant.message === null) {
            const missing = `v:${String(variant.variantIndex)}:missing`;
            labels.push(missing);
            avatars.push(missing);
            continue;
        }
        const prefix = `v:${String(variant.variantIndex)}:${variant.domId ?? ''}:`;
        if (variant.presentation === null) {
            throw new Error('Chat comparison presentation signature is missing');
        }
        const role = variant.presentation.normalizedRole;
        labels.push(`${prefix}${resolveMessageSenderLabelCacheSignature(host, variant.message, role)}`);
        avatars.push(`${prefix}${resolveMessageAvatarCacheSignature(host, snapshot, role)}`);
    }
    return { label: labels.join('|'), avatar: avatars.join('|') };
};

const resolveConversationEntryCacheSignature = (host: ChatCurrentConversationRenderDependencies, entry: ConversationRenderEntry, isCurrentStreaming: boolean, snapshot: ConversationPresentationSignatureSnapshot): string => {
    const baseSignature = resolveConversationRenderEntrySignature(entry, { isCurrentStreaming });
    const presentation = resolveConversationEntryPresentationCacheSignatures(host, entry, snapshot);
    return `${baseSignature}|labels:${presentation.label}|avatars:${presentation.avatar}`;
};

const traverseConversationRenderEntries = (host: ChatCurrentConversationRenderDependencies, renderEntries: ConversationRenderEntry[], isCurrentStreaming: boolean, visit: (entry: ConversationRenderEntry, domId: string, signature: string) => void): void => {
    const presentationSnapshot = createConversationPresentationSignatureSnapshot();
    for (const entry of renderEntries) {
        const domId = entry.domId;
        if (!domId) continue;
        visit(entry, domId, resolveConversationEntryCacheSignature(host, entry, isCurrentStreaming, presentationSnapshot));
    }
};

const buildConversationRenderPlan = (host: ChatCurrentConversationRenderDependencies, renderEntries: ConversationRenderEntry[], isCurrentStreaming: boolean): { domIdsInOrder: string[]; domIdSet: Set<string>; signatureByDomId: Map<string, string> } => {
    const domIdsInOrder: string[] = [];
    const domIdSet = new Set<string>();
    const signatures = new Map<string, string>();
    traverseConversationRenderEntries(host, renderEntries, isCurrentStreaming, (_entry, domId, signature) => {
        domIdsInOrder.push(domId);
        domIdSet.add(domId);
        signatures.set(domId, signature);
    });
    return { domIdsInOrder, domIdSet, signatureByDomId: signatures };
};

const prepareConversationMarkup = async (inputArguments: RenderCurrentConversationMessageStateArguments, signatures: ReadonlyMap<string, string>, unchangedDomIds: ReadonlySet<string>, prepareRoots: boolean): Promise<Map<string, PreparedConversationEntry> | null> => {
    const preparedEntriesByDomId = new Map<string, PreparedConversationEntry>();
    let sliceStartedAt = monotonicMs();
    for (const entry of inputArguments.renderEntries) {
        const domId = entry.domId;
        if (!domId || unchangedDomIds.has(domId)) continue;
        if (!inputArguments.isCurrent()) return null;
        const markup = renderConversationEntryMarkup(inputArguments.host, entry, inputArguments.conversationKey);
        const replacement = prepareRoots && entry.type === 'message' && entry.presentation.normalizedRole !== 'assistant' ? applyConversationEntryMutation({ intent: 'insert', documentRef: inputArguments.container.ownerDocument, nextMarkup: markup, messageDomId: domId, animate: false }).root : undefined;
        preparedEntriesByDomId.set(domId, { markup, replacement });
        if (monotonicMs() - sliceStartedAt >= 6) {
            await waitForTimerDelay(inputArguments.container.ownerDocument.defaultView, 0, null);
            sliceStartedAt = monotonicMs();
        }
    }
    if (!inputArguments.isCurrent()) return null;
    if (preparedEntriesByDomId.size > 0) await waitForTimerDelay(inputArguments.container.ownerDocument.defaultView, 0, null);
    if (!inputArguments.isCurrent()) return null;
    const currentPlan = buildConversationRenderPlan(inputArguments.host, inputArguments.renderEntries, inputArguments.isCurrentStreaming);
    if (currentPlan.signatureByDomId.size !== signatures.size) return null;
    for (const [domId, signature] of signatures) {
        if (currentPlan.signatureByDomId.get(domId) !== signature) return null;
    }
    return preparedEntriesByDomId;
};

const renderCurrentConversationMessageState = async (inputArguments: RenderCurrentConversationMessageStateArguments): Promise<'unchanged' | 'updated' | 'superseded'> => {
    const renderPlan = buildConversationRenderPlan(inputArguments.host, inputArguments.renderEntries, inputArguments.isCurrentStreaming);
    const shouldBulkRender = !inputArguments.previousCache || inputArguments.previousCache.conversationKey !== inputArguments.conversationKey || inputArguments.previousCache.viewState !== 'messages';
    const existingBeforePreparation = ConversationMessageDomReconcileController.resolveExistingMessageNodes(inputArguments.container);
    const refreshesBeforePreparation = inputArguments.previousCache === null ? [] : ConversationMessageDomReconcileController.resolveEntryRefreshes({ renderEntries: inputArguments.renderEntries, cache: inputArguments.previousCache, nodesByDomId: existingBeforePreparation.byId, renderSignatureByDomId: renderPlan.signatureByDomId, isCurrentStreaming: inputArguments.isCurrentStreaming });
    const refreshDomIds = new Set(refreshesBeforePreparation.map((refresh) => refresh.entry.domId));
    const unchangedDomIds = new Set(shouldBulkRender ? [] : renderPlan.domIdsInOrder.filter((domId) => existingBeforePreparation.byId.has(domId) && !refreshDomIds.has(domId)));
    const preparedEntriesByDomId = await prepareConversationMarkup(inputArguments, renderPlan.signatureByDomId, unchangedDomIds, !shouldBulkRender);
    if (preparedEntriesByDomId === null || !inputArguments.isCurrent() || inputArguments.host.viewState.conversationRenderCache !== inputArguments.previousCache) return 'superseded';
    const cache = getOrCreateConversationRenderCache(inputArguments.host, { conversationKey: inputArguments.conversationKey, viewState: 'messages' });
    if (shouldBulkRender) {
        const parts = [...preparedEntriesByDomId.values()].map((prepared) => prepared.markup);
        if (inputArguments.showEarlierMessagesLoading) parts.unshift(renderMessageWindowLoadingMarkup('before'));
        if (inputArguments.showNewerMessagesLoading) parts.push(renderMessageWindowLoadingMarkup('after'));
        const bulkCache = createConversationRenderCache({ conversationKey: inputArguments.conversationKey, viewState: 'messages' });
        replaceConversationRenderCacheIndex({ cache: bulkCache, domIdsInOrder: renderPlan.domIdsInOrder, signatures: renderPlan.signatureByDomId });
        inputArguments.host.viewState.conversationRenderCache = bulkCache;
        inputArguments.host.pageDom.updateHtml(inputArguments.container, joinUiHtml(parts), { escape: false });
        inputArguments.host.conversationRuntime.requireMessages().postRenderRequest(inputArguments.container, 'initialConversation');
        bulkCache.renderedHistory = inputArguments.history;
        return 'updated';
    }

    const expectedDomIds = renderPlan.domIdsInOrder;
    const existing = existingBeforePreparation;
    const nextSignatureByDomId = renderPlan.signatureByDomId;
    const structureMatches = !existing.hasUnstableEntries && arraysEqual(existing.idsInOrder, expectedDomIds);
    let entryRefreshes = structureMatches ? ConversationMessageDomReconcileController.resolveEntryRefreshes({ renderEntries: inputArguments.renderEntries, cache, nodesByDomId: existing.byId, renderSignatureByDomId: nextSignatureByDomId, isCurrentStreaming: inputArguments.isCurrentStreaming }) : [];
    const messageDomStable = structureMatches && arraysEqual(cache.domIdsInOrder, expectedDomIds) && entryRefreshes.length === 0;
    const loadingVisibility = {
        showEarlier: inputArguments.showEarlierMessagesLoading,
        showNewer: inputArguments.showNewerMessagesLoading
    };
    if (messageDomStable && messageWindowLoadingElementsMatch(inputArguments.container, loadingVisibility, existing.entriesInOrder)) {
        cache.renderedHistory = inputArguments.history;
        return 'unchanged';
    }
    let loadingElementsUpdated = false;
    const postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[] = [];
    const reconcile = (): void => {
        let currentEntries = existing.entriesInOrder;
        if (!messageDomStable) {
            let finalNodesByDomId = existing.byId;
            if (!structureMatches) {
                const reconcileResult = ConversationMessageDomReconcileController.reconcileConversationDom({
                    container: inputArguments.container,
                    renderEntries: inputArguments.renderEntries,
                    renderSignatureByDomId: nextSignatureByDomId,
                    expectedDomIds: renderPlan.domIdSet,
                    existing,
                    cache,
                    isCurrentStreaming: inputArguments.isCurrentStreaming,
                    preparedEntriesByDomId
                });
                postRenderRequests.push(...reconcileResult.postRenderRequests);
                for (const removedId of reconcileResult.removedIds) {
                    deleteConversationRenderCacheSignature(cache, removedId);
                }
                finalNodesByDomId = reconcileResult.finalNodesByDomId;
                entryRefreshes = ConversationMessageDomReconcileController.resolveEntryRefreshes({ renderEntries: inputArguments.renderEntries, cache, nodesByDomId: finalNodesByDomId, renderSignatureByDomId: nextSignatureByDomId, isCurrentStreaming: inputArguments.isCurrentStreaming });
            }

            postRenderRequests.push(
                ...ConversationMessageDomReconcileController.refreshMessageMarkupIfNeeded({
                    refreshes: entryRefreshes,
                    cache,
                    isCurrentStreaming: inputArguments.isCurrentStreaming,
                    preparedEntriesByDomId
                })
            );
            currentEntries = resolveConversationEntryElements(inputArguments.container);
        }

        loadingElementsUpdated = syncMessageWindowLoadingElements(inputArguments.container, loadingVisibility, currentEntries);
        if (postRenderRequests.length > 0) inputArguments.host.conversationRuntime.requireMessages().postRenderRequests(postRenderRequests);
    };
    if (inputArguments.viewportStabilityScope === 'caller') reconcile();
    else withAssistantViewportStability(inputArguments.container, reconcile);
    cache.renderedHistory = inputArguments.history;
    if (messageDomStable) {
        return loadingElementsUpdated ? 'updated' : 'unchanged';
    }
    replaceConversationRenderCacheIndex({ cache, domIdsInOrder: expectedDomIds, signatures: nextSignatureByDomId });
    return 'updated';
};

export { renderCurrentConversationMessageState };
