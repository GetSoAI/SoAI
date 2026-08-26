/* SoAI - Page-owned streaming message DOM patch scheduler for chat conversations [frontend/assets/ts/pages/chat/controllers/page/renderer/chatStreamRenderCoordinatorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { CHAT_SELECTORS, createStreamingElementCache, isChatMessageDomOwnedByLiveContainer, isConversationStreamingUiActive, normalizeConversationId, renderStreamingMessageContent, resolveStreamRenderQueueKey, type ActiveStreamRenderPatchType, type ChatMessage, type ChatStreamRenderRuntime, type ChatStreamingControllerContext, type PendingRender, type StreamRenderPatchType } from '@features/chat/public.ts';
import { bindStreamingElementCacheIdentity, cachedStreamingElementsMatchIdentity, resolveStreamingMessageDomIdentity, type StreamingMessageDomIdentity } from '@pages/chat/controllers/page/renderer/streamingMessageDomIdentityManager.ts';
import { reconcileActivityDurationRegistry } from '@pages/chat/controllers/page/durations/service.ts';

const resolveMergedPatchType = (current: StreamRenderPatchType, next: StreamRenderPatchType): StreamRenderPatchType => {
    if (current === 'terminal') return next;
    if (next === 'terminal') return current;
    if (current === 'none') return next;
    if (next === 'none') return current;
    if (current === next) return current;
    if (current === 'both' || next === 'both') return 'both';
    if (current === 'passive-state') return next;
    if (next === 'passive-state') return current;
    return 'both';
};

const mergeContiguousTextAppends = (existing: PendingRender, next: PendingRender): PendingRender['textAppend'] => {
    if (existing.textAppend === null || next.textAppend === null || existing.assistantRevision === null) {
        return null;
    }
    const existingEndContentLength = existing.textAppend.baseContentLength + existing.textAppend.textDelta.length;
    if (existing.assistantRevision !== next.textAppend.baseAssistantRevision || existingEndContentLength !== next.textAppend.baseContentLength || existing.textAppend.nextTimelineLength > next.textAppend.nextTimelineLength) {
        return null;
    }
    return {
        baseAssistantRevision: existing.textAppend.baseAssistantRevision,
        baseContentLength: existing.textAppend.baseContentLength,
        nextTimelineLength: next.textAppend.nextTimelineLength,
        textDelta: `${existing.textAppend.textDelta}${next.textAppend.textDelta}`
    };
};

const mergePendingRender = (existing: PendingRender | undefined, next: PendingRender): PendingRender => {
    if (existing === undefined) return next;
    const patchType = resolveMergedPatchType(existing.patchType, next.patchType);
    const textAppend = patchType === 'text-delta' ? mergeContiguousTextAppends(existing, next) : null;
    return {
        message: next.message,
        conversationId: next.conversationId,
        patchType,
        assistantRevision: next.assistantRevision,
        textAppend
    };
};

const invalidateElementCache = (context: ChatStreamingControllerContext): void => {
    context.cachedStreamingElements = null;
};

const isActivePendingRender = (render: PendingRender): render is PendingRender & { patchType: ActiveStreamRenderPatchType } => render.patchType !== 'terminal';

const getOrCreateElementCache = (context: ChatStreamingControllerContext, message: ChatMessage, conversationId: string): NonNullable<typeof context.cachedStreamingElements> | null => {
    if (!context.presentationActive) {
        return null;
    }
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return null;
    }
    const messagesArea = context.dependencies.presentation.optionalUI(CHAT_SELECTORS.MESSAGES);
    if (!(messagesArea instanceof HTMLElement) || !messagesArea.isConnected) {
        return null;
    }
    const matchedCached = cachedStreamingElementsMatchIdentity(context, message, normalizedConversationId, messagesArea);
    if (matchedCached !== null) {
        return matchedCached;
    }
    let identity: StreamingMessageDomIdentity;
    try {
        identity = resolveStreamingMessageDomIdentity(context, message, normalizedConversationId);
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', 'Failed to resolve streaming message DOM id', ensureError(error));
        return null;
    }
    const messageDomId = identity.messageDomId;
    const cached = context.cachedStreamingElements;
    if (
        cached &&
        cached.conversationId === normalizedConversationId &&
        cached.messageDomId === messageDomId &&
        cached.messagesArea === messagesArea &&
        isChatMessageDomOwnedByLiveContainer({
            liveContainer: messagesArea,
            messageRoot: cached.messageRoot,
            messageDomId,
            messageText: cached.messageText
        })
    ) {
        bindStreamingElementCacheIdentity(cached, message, identity);
        return cached;
    }
    const nextCache = createStreamingElementCache({
        conversationId: normalizedConversationId,
        messagesArea,
        messageDomId
    });
    if (
        !nextCache.messageRoot ||
        !nextCache.messageText ||
        !isChatMessageDomOwnedByLiveContainer({
            liveContainer: messagesArea,
            messageRoot: nextCache.messageRoot,
            messageDomId,
            messageText: nextCache.messageText
        })
    ) {
        return null;
    }
    bindStreamingElementCacheIdentity(nextCache, message, identity);
    context.cachedStreamingElements = nextCache;
    return nextCache;
};

const renderMessageContent = (context: ChatStreamingControllerContext, render: PendingRender & { patchType: ActiveStreamRenderPatchType }): { handled: boolean; updatedMarkup: boolean; target: HTMLElement | null } => {
    const cached = getOrCreateElementCache(context, render.message, render.conversationId);
    if (!cached) {
        invalidateElementCache(context);
        return { handled: false, updatedMarkup: false, target: null };
    }
    const { handled, invalidatedCache, updatedMarkup, target } = renderStreamingMessageContent({
        message: render.message,
        cached,
        patchType: render.patchType,
        assistantRevision: render.assistantRevision,
        textAppend: render.textAppend,
        messageManager: context.dependencies.messageManager
    });
    if (invalidatedCache) {
        invalidateElementCache(context);
        return { handled: false, updatedMarkup: false, target: null };
    }
    if (!(target instanceof HTMLElement)) {
        throw new Error('Streaming message render target is unavailable');
    }
    return { handled, updatedMarkup, target };
};

const updateStreamingMessage = (context: ChatStreamingControllerContext, render: PendingRender & { patchType: ActiveStreamRenderPatchType }): { handled: boolean; updatedMarkup: boolean; target: HTMLElement | null } => {
    if (render.patchType === 'none') {
        return { handled: false, updatedMarkup: false, target: null };
    }
    if (context.isRenderInProgress) {
        context.scheduleStreamRender?.(render);
        return { handled: true, updatedMarkup: false, target: null };
    }
    context.isRenderInProgress = true;
    try {
        return renderMessageContent(context, render);
    } finally {
        context.isRenderInProgress = false;
    }
};

const isMountedAssistantMessageSettled = (context: ChatStreamingControllerContext, message: ChatMessage, conversationId: string): boolean => {
    const cached = getOrCreateElementCache(context, message, conversationId);
    if (!cached?.messageRoot) {
        return false;
    }
    const actions = dom.resolve('.message-actions', cached.messageRoot);
    return actions instanceof HTMLElement && actions.getAttribute('data-message-streaming') === 'false';
};

const recoverMissingIncrementalPatchTarget = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const currentConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    if (!currentConversationId || currentConversationId !== normalizeConversationId(conversationId) || context.missingTargetRecoveryConversationId === currentConversationId) {
        return;
    }
    context.missingTargetRecoveryConversationId = currentConversationId;
    void context.dependencies.presentation
        .renderCurrentConversation()
        .catch((error: Error) => {
            context.errorHandler?.debug?.('ChatStream', 'Failed to recover missing streaming patch target', ensureError(error));
        })
        .finally(() => {
            if (!context.disposed && context.missingTargetRecoveryConversationId === currentConversationId) {
                context.missingTargetRecoveryConversationId = null;
            }
        });
};

const applyScheduledStreamRender = (context: ChatStreamingControllerContext, render: PendingRender): void => {
    if (!context.presentationActive) return;
    if (render.patchType === 'none') return;
    if (!isActivePendingRender(render)) return;
    const currentConversationId = normalizeConversationId(context.dependencies.state.getCurrentConversationId());
    if (!currentConversationId || currentConversationId !== normalizeConversationId(render.conversationId)) {
        return;
    }
    const streamingUiActive = isConversationStreamingUiActive(context, render.conversationId);
    if (!streamingUiActive) {
        if (render.patchType !== 'timeline-activity' || isMountedAssistantMessageSettled(context, render.message, render.conversationId)) {
            return;
        }
    }
    const uiManager = context.dependencies.uiManager;
    const shouldAutoScroll = uiManager.shouldAutoScrollAfterContentUpdate();
    if (!shouldAutoScroll && uiManager.isAutoScrollEnabled()) {
        uiManager.setAutoScrollEnabled(false);
    }
    const renderResult = updateStreamingMessage(context, render);
    if (!renderResult.handled) {
        recoverMissingIncrementalPatchTarget(context, render.conversationId);
        return;
    }
    if (renderResult.target) {
        context.reconcileActivityDurations?.(renderResult.target, render.conversationId);
    }
    if (shouldAutoScroll && render.patchType !== 'passive-state' && renderResult.updatedMarkup) {
        if (!uiManager.isAutoScrollEnabled()) {
            uiManager.setAutoScrollEnabled(true);
        }
        uiManager.scrollToBottom();
    }
};

const createScheduledStreamRender = (context: ChatStreamingControllerContext): ChatStreamRenderRuntime['scheduleStreamRender'] => {
    const queue = new AnimationFrameRenderQueue<PendingRender>({
        label: 'ChatStreamRenderCoordinator',
        keyOf: (render) => resolveStreamRenderQueueKey(render.message, render.conversationId),
        merge: (previous, next) => mergePendingRender(previous ?? undefined, next),
        renderBatch: (renders) => {
            for (const render of renders) {
                if (context.disposed || !context.presentationActive) {
                    return;
                }
                applyScheduledStreamRender(context, render);
            }
        },
        isDisposed: () => context.disposed
    });
    function scheduledRender(render: PendingRender): void {
        if (!context.presentationActive) {
            return;
        }
        queue.schedule(render);
    }
    scheduledRender.drop = (message: ChatMessage, conversationId: string): boolean => {
        return queue.drop(resolveStreamRenderQueueKey(message, conversationId));
    };
    scheduledRender.cancel = (): void => {
        queue.cancel();
    };
    return scheduledRender;
};

const createChatStreamRenderCoordinator = (context: ChatStreamingControllerContext): ChatStreamRenderRuntime => {
    const reconcileActivityDurations = (root: Element, conversationId: string): void => {
        const viewport = context.dependencies.presentation.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
        if (!(viewport instanceof HTMLElement) || context.disposed || !context.presentationActive || !viewport.isConnected) {
            return;
        }
        reconcileActivityDurationRegistry({
            viewport,
            root,
            conversationId
        });
    };
    return {
        scheduleStreamRender: createScheduledStreamRender(context),
        reconcileActivityDurations
    };
};

export { createChatStreamRenderCoordinator };
