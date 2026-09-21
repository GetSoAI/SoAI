/* SoAI - Chat page current conversation message controller [frontend/assets/ts/pages/chat/controllers/page/renderer/currentConversationMessageController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml } from '@core/security/uiHtml.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { resolveConversationEntryElements, resolveConversationRenderEntrySignature, withAssistantViewportStability, type ConversationMessage, type ConversationRenderEntry } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies, ConversationRenderCache } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { ConversationMessageDomReconcileController } from '@pages/chat/controllers/page/renderer/ConversationMessageDomReconcileController.ts';
import { renderConversationEntryMarkup } from '@pages/chat/controllers/page/renderer/conversationEntryRendererController.ts';
import { messageWindowLoadingElementsMatch, renderMessageWindowLoadingMarkup, syncMessageWindowLoadingElements } from '@pages/chat/controllers/page/renderer/currentConversationMessageWindowLoadingController.ts';
import { createConversationRenderCache, deleteConversationRenderCacheSignature, getOrCreateConversationRenderCache, replaceConversationRenderCacheIndex, setConversationRenderCacheSignature } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';

type RenderCurrentConversationMessageStateArguments = {
    host: ChatCurrentConversationRenderDependencies;
    container: Element;
    previousCache: ConversationRenderCache | null;
    conversationKey: string;
    renderEntries: ConversationRenderEntry[];
    isCurrentStreaming: boolean;
    showEarlierMessagesLoading: boolean;
    showNewerMessagesLoading: boolean;
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

const buildConversationMessagesMarkup = (host: ChatCurrentConversationRenderDependencies, inputArguments: { conversationKey: string; renderEntries: ConversationRenderEntry[]; isCurrentStreaming: boolean; showEarlierMessagesLoading: boolean; showNewerMessagesLoading: boolean }): { markup: TrustedHtml; cache: ConversationRenderCache } => {
    const parts: TrustedHtml[] = [];
    const cache = createConversationRenderCache({ conversationKey: inputArguments.conversationKey, viewState: 'messages' });
    if (inputArguments.showEarlierMessagesLoading) {
        parts.push(renderMessageWindowLoadingMarkup('before'));
    }
    traverseConversationRenderEntries(host, inputArguments.renderEntries, inputArguments.isCurrentStreaming, (entry, domId, signature) => {
        const markup = renderConversationEntryMarkup(host, entry, inputArguments.conversationKey);
        setConversationRenderCacheSignature({ cache, domId, signature });
        cache.domIdsInOrder.push(domId);
        parts.push(markup);
    });
    if (inputArguments.showNewerMessagesLoading) {
        parts.push(renderMessageWindowLoadingMarkup('after'));
    }
    return { markup: joinUiHtml(parts), cache };
};

const renderCurrentConversationMessageState = (inputArguments: RenderCurrentConversationMessageStateArguments): 'unchanged' | 'updated' => {
    const cache = getOrCreateConversationRenderCache(inputArguments.host, { conversationKey: inputArguments.conversationKey, viewState: 'messages' });
    const shouldBulkRender = !inputArguments.previousCache || inputArguments.previousCache.conversationKey !== inputArguments.conversationKey || inputArguments.previousCache.viewState !== 'messages';
    if (shouldBulkRender) {
        const bulk = buildConversationMessagesMarkup(inputArguments.host, {
            conversationKey: inputArguments.conversationKey,
            renderEntries: inputArguments.renderEntries,
            isCurrentStreaming: inputArguments.isCurrentStreaming,
            showEarlierMessagesLoading: inputArguments.showEarlierMessagesLoading,
            showNewerMessagesLoading: inputArguments.showNewerMessagesLoading
        });
        inputArguments.host.viewState.conversationRenderCache = bulk.cache;
        inputArguments.host.pageDom.updateHtml(inputArguments.container, bulk.markup, { escape: false });
        inputArguments.host.conversationRuntime.requireMessages().postRenderRequest(inputArguments.container, 'initialConversation');
        return 'updated';
    }

    const renderPlan = buildConversationRenderPlan(inputArguments.host, inputArguments.renderEntries, inputArguments.isCurrentStreaming);
    const expectedDomIds = renderPlan.domIdsInOrder;
    const existing = ConversationMessageDomReconcileController.resolveExistingMessageNodes(inputArguments.container);
    const nextSignatureByDomId = renderPlan.signatureByDomId;
    const structureMatches = !existing.hasUnstableEntries && arraysEqual(existing.idsInOrder, expectedDomIds);
    let entryRefreshes = structureMatches ? ConversationMessageDomReconcileController.resolveEntryRefreshes({ renderEntries: inputArguments.renderEntries, cache, nodesByDomId: existing.byId, renderSignatureByDomId: nextSignatureByDomId, isCurrentStreaming: inputArguments.isCurrentStreaming }) : [];
    const messageDomStable = structureMatches && arraysEqual(cache.domIdsInOrder, expectedDomIds) && entryRefreshes.length === 0;
    const loadingVisibility = {
        showEarlier: inputArguments.showEarlierMessagesLoading,
        showNewer: inputArguments.showNewerMessagesLoading
    };
    if (messageDomStable && messageWindowLoadingElementsMatch(inputArguments.container, loadingVisibility, existing.entriesInOrder)) return 'unchanged';
    let loadingElementsUpdated = false;
    withAssistantViewportStability(inputArguments.container, () => {
        let currentEntries = existing.entriesInOrder;
        if (!messageDomStable) {
            let finalNodesByDomId = existing.byId;
            if (!structureMatches) {
                const reconcileResult = ConversationMessageDomReconcileController.reconcileConversationDom({
                    host: inputArguments.host,
                    container: inputArguments.container,
                    conversationId: inputArguments.conversationKey,
                    renderEntries: inputArguments.renderEntries,
                    renderSignatureByDomId: nextSignatureByDomId,
                    expectedDomIds: renderPlan.domIdSet,
                    existing,
                    cache,
                    isCurrentStreaming: inputArguments.isCurrentStreaming
                });
                for (const request of reconcileResult.postRenderRequests) {
                    inputArguments.host.conversationRuntime.requireMessages().postRenderRequest(request.root, request.type);
                }
                for (const removedId of reconcileResult.removedIds) {
                    deleteConversationRenderCacheSignature(cache, removedId);
                }
                finalNodesByDomId = reconcileResult.finalNodesByDomId;
                entryRefreshes = ConversationMessageDomReconcileController.resolveEntryRefreshes({ renderEntries: inputArguments.renderEntries, cache, nodesByDomId: finalNodesByDomId, renderSignatureByDomId: nextSignatureByDomId, isCurrentStreaming: inputArguments.isCurrentStreaming });
            }

            ConversationMessageDomReconcileController.refreshMessageMarkupIfNeeded({
                host: inputArguments.host,
                conversationId: inputArguments.conversationKey,
                refreshes: entryRefreshes,
                cache,
                isCurrentStreaming: inputArguments.isCurrentStreaming
            });
            currentEntries = resolveConversationEntryElements(inputArguments.container);
        }

        loadingElementsUpdated = syncMessageWindowLoadingElements(inputArguments.container, loadingVisibility, currentEntries);
    });
    if (messageDomStable) {
        return loadingElementsUpdated ? 'updated' : 'unchanged';
    }
    replaceConversationRenderCacheIndex({ cache, domIdsInOrder: expectedDomIds, signatures: nextSignatureByDomId });
    return 'updated';
};

export { renderCurrentConversationMessageState };
