/* SoAI - Chat feature message state [frontend/assets/ts/features/chat/message/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { createAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { resolveStableMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { resolveChatMessageSegmentProjectionSignature } from '@features/chat/message/messageSegmentProjectionSignature.ts';
import { resolveAssistantRevisionFromMessage, resolveMessageContentSegmentsForRendering } from '@features/chat/message/messageSegmentsResolution.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { flattenTextFragments } from '@features/chat/message/messageTextFlattening.ts';
import { resolveMessageReferenceFromConversation, type ResolvedMessageReference } from '@features/chat/message/messageReferenceResolution.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import { resolveChatMessageRenderSignature } from '@features/chat/message/messageRenderSignature.ts';
import { isSettledAssistantHtml } from '@features/chat/message/assistantSettledDom.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveRunningActivitySummary, resolveRunningActivitySummaryFingerprint, type RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { formatAssistantVariantIdentityKey } from '@features/chat/message/assistantMessageIdentity.ts';

type PreRenderedAssistantBodyCacheEntry = {
    html: string;
    signature: string;
    workerEpoch: number;
};

type RunningActivitySummaryCacheEntry = {
    fingerprint: string;
    summary: RunningActivitySummary;
    validUntilMs: number;
};

class ChatMessageState {
    #assistantTimelineIndexCache: WeakMap<ChatMessage, AssistantTimelineIndexState>;
    #assistantTimelineIndexReadyForReuse: WeakSet<ChatMessage>;
    #segmentsCache: WeakMap<ChatMessage, { assistantRevision: number; segmentProjectionSignature: string; segments: MessageSegment[] }>;
    #preRenderedAssistantBodyHtmlCache: WeakMap<ChatMessage, PreRenderedAssistantBodyCacheEntry>;
    #loadingActivityCollapsedStateByMessage: WeakMap<ChatMessage, boolean>;
    #loadingActivityCollapsedStateByStableId: Map<string, boolean>;
    #runningActivitySummaryByMessage: WeakMap<ChatMessage, RunningActivitySummaryCacheEntry>;
    #runningActivitySummaryByStableId: Map<string, RunningActivitySummaryCacheEntry>;

    constructor() {
        this.#assistantTimelineIndexCache = new WeakMap();
        this.#assistantTimelineIndexReadyForReuse = new WeakSet();
        this.#segmentsCache = new WeakMap();
        this.#preRenderedAssistantBodyHtmlCache = new WeakMap();
        this.#loadingActivityCollapsedStateByMessage = new WeakMap();
        this.#loadingActivityCollapsedStateByStableId = new Map();
        this.#runningActivitySummaryByMessage = new WeakMap();
        this.#runningActivitySummaryByStableId = new Map();
    }

    isMessageContract<T>(value: T): value is T & ChatMessage {
        return isJsonObject(value) && ('role' in value || 'content' in value);
    }

    getMessageTextFragments(message: ChatMessage): string[] {
        return flattenTextFragments(message.content);
    }

    #invalidateProjectionDerivedCaches(message: ChatMessage): void {
        this.#assistantTimelineIndexReadyForReuse.delete(message);
        this.#segmentsCache.delete(message);
        this.#preRenderedAssistantBodyHtmlCache.delete(message);
        this.#runningActivitySummaryByMessage.delete(message);
        const summaryStableId = this.#resolveStableAssistantVariantCacheId(message);
        if (summaryStableId !== null) {
            this.#runningActivitySummaryByStableId.delete(summaryStableId);
        }
    }

    invalidateMessageCache(message: ChatMessage | null | undefined): void {
        if (!message || !isObject(message)) {
            return;
        }

        this.#assistantTimelineIndexCache.delete(message);
        this.#invalidateProjectionDerivedCaches(message);
    }

    invalidateMessageProjectionCache(message: ChatMessage | null | undefined): void {
        if (!message || !isObject(message)) {
            return;
        }
        this.#invalidateProjectionDerivedCaches(message);
    }

    clearCache(): void {
        this.#assistantTimelineIndexCache = new WeakMap();
        this.#assistantTimelineIndexReadyForReuse = new WeakSet();
        this.#segmentsCache = new WeakMap();
        this.#runningActivitySummaryByMessage = new WeakMap();
        this.#runningActivitySummaryByStableId = new Map();
        this.resetPreRenderedAssistantBodyCache();
    }

    #requireAssistantTimelineIndexState(message: ChatMessage): AssistantTimelineIndexState {
        const existing = this.#assistantTimelineIndexCache.get(message);
        if (existing) {
            return existing;
        }
        const created = createAssistantTimelineIndexState();
        this.#assistantTimelineIndexCache.set(message, created);
        return created;
    }

    resetPreRenderedAssistantBodyCache(): void {
        this.#preRenderedAssistantBodyHtmlCache = new WeakMap();
        this.#loadingActivityCollapsedStateByMessage = new WeakMap();
        this.#loadingActivityCollapsedStateByStableId = new Map();
    }

    storePreRenderedAssistantBodyHtml(message: ChatMessage, html: string, workerEpoch: number): void {
        if (!isSettledAssistantHtml(html)) {
            throw new Error('Pre-rendered assistant body cache received transient assistant markup.');
        }
        this.#preRenderedAssistantBodyHtmlCache.set(message, {
            html,
            signature: resolveChatMessageRenderSignature(message, null),
            workerEpoch
        });
    }

    getPreRenderedAssistantBodyHtml(message: ChatMessage, workerEpoch: number): string | null {
        const existing = this.#preRenderedAssistantBodyHtmlCache.get(message);
        if (existing === undefined) {
            return null;
        }
        if (existing.workerEpoch !== workerEpoch || existing.signature !== resolveChatMessageRenderSignature(message, null)) {
            this.#preRenderedAssistantBodyHtmlCache.delete(message);
            return null;
        }
        return existing.html;
    }

    #resolveStableMessageIdForLoadingState(message: ChatMessage): string | null {
        if (message.role === 'assistant') {
            if (
                resolveAssistantVariantIdentity({
                    assistantTurnTimestamp: message.assistantTurnAtMs,
                    modelVariantIndex: message.modelVariantIndex
                }) === null
            ) {
                return null;
            }
        }
        return resolveStableMessageDomId(message);
    }

    #resolveStableAssistantVariantCacheId(message: ChatMessage): string | null {
        if (message.role !== 'assistant') {
            return null;
        }
        const identity = resolveAssistantVariantIdentity({
            assistantTurnTimestamp: message.assistantTurnAtMs,
            modelVariantIndex: message.modelVariantIndex
        });
        if (identity === null) {
            return null;
        }
        return formatAssistantVariantIdentityKey(identity);
    }

    #readRunningActivitySummaryCache(message: ChatMessage, fingerprint: string, nowMs: number): RunningActivitySummary | null {
        const stableId = this.#resolveStableAssistantVariantCacheId(message);
        const cached = stableId === null ? this.#runningActivitySummaryByMessage.get(message) : this.#runningActivitySummaryByStableId.get(stableId);
        if (cached === undefined || cached.fingerprint !== fingerprint || nowMs >= cached.validUntilMs) {
            return null;
        }
        return cached.summary;
    }

    #writeRunningActivitySummaryCache(message: ChatMessage, fingerprint: string, summary: RunningActivitySummary): void {
        const entry: RunningActivitySummaryCacheEntry = {
            fingerprint,
            summary,
            validUntilMs: summary.nextVisibleAtMs === null ? Number.POSITIVE_INFINITY : summary.nextVisibleAtMs
        };
        const stableId = this.#resolveStableAssistantVariantCacheId(message);
        if (stableId === null) {
            this.#runningActivitySummaryByMessage.set(message, entry);
            return;
        }
        this.#runningActivitySummaryByStableId.set(stableId, entry);
    }

    #resolveRunningActivitySummaryWithTimelineIndex(message: ChatMessage, nowMs: number, terminalState: boolean | null = null): RunningActivitySummary {
        const timelineIndexState = this.#assistantTimelineIndexReadyForReuse.has(message) ? (this.#assistantTimelineIndexCache.get(message) ?? null) : null;
        try {
            return resolveRunningActivitySummary(message, nowMs, timelineIndexState, terminalState);
        } catch (error) {
            if (timelineIndexState !== null) {
                this.#assistantTimelineIndexReadyForReuse.delete(message);
                this.#assistantTimelineIndexCache.delete(message);
            }
            throw error;
        }
    }

    resolveRunningActivitySummary(message: ChatMessage, nowMs: number): RunningActivitySummary {
        const fingerprint = resolveRunningActivitySummaryFingerprint(message);
        if (fingerprint === null) {
            return this.#resolveRunningActivitySummaryWithTimelineIndex(message, nowMs);
        }
        const cached = this.#readRunningActivitySummaryCache(message, fingerprint.cacheKey, nowMs);
        if (cached !== null) {
            return cached;
        }
        const summary = this.#resolveRunningActivitySummaryWithTimelineIndex(message, nowMs, fingerprint.terminal);
        this.#writeRunningActivitySummaryCache(message, fingerprint.cacheKey, summary);
        return summary;
    }

    resolveRunningActivitySummaryForMarkup(message: ChatMessage, nowMs: number): RunningActivitySummary {
        return this.#resolveRunningActivitySummaryWithTimelineIndex(message, nowMs);
    }

    getLoadingActivityCollapsedState(message: ChatMessage): boolean | null {
        const stableId = this.#resolveStableMessageIdForLoadingState(message);
        if (typeof stableId === 'string') {
            const stableState = this.#loadingActivityCollapsedStateByStableId.get(stableId);
            if (stableState !== undefined) {
                return stableState;
            }
        }
        const existing = this.#loadingActivityCollapsedStateByMessage.get(message);
        return existing === undefined ? null : existing;
    }

    toggleLoadingActivityCollapsedState(message: ChatMessage, defaultCollapsed: boolean): boolean {
        const currentCollapsed = this.getLoadingActivityCollapsedState(message) ?? defaultCollapsed;
        const nextCollapsed = !currentCollapsed;
        this.#loadingActivityCollapsedStateByMessage.set(message, nextCollapsed);
        const stableId = this.#resolveStableMessageIdForLoadingState(message);
        if (typeof stableId === 'string') {
            this.#loadingActivityCollapsedStateByStableId.set(stableId, nextCollapsed);
        }
        return nextCollapsed;
    }

    resolveMessageContentSegments(message: ChatMessage | null | undefined): MessageSegment[] {
        if (!message) {
            return [];
        }
        const assistantRevision = isAssistantMessageRole(message) ? resolveAssistantRevisionFromMessage(message) : null;
        const timelineIndexState = isAssistantMessageRole(message) ? this.#requireAssistantTimelineIndexState(message) : null;
        const nowMs = serverEpochMs();
        try {
            if (timelineIndexState !== null) {
                updateAssistantTimelineIndexState(timelineIndexState, message);
            }
            const segmentProjectionSignature = isAssistantMessageRole(message) ? resolveChatMessageSegmentProjectionSignature(message, timelineIndexState) : null;
            let resolved: MessageSegment[] | null = null;
            if (assistantRevision !== null) {
                const cached = this.#segmentsCache.get(message);
                if (cached && cached.assistantRevision === assistantRevision && cached.segmentProjectionSignature === segmentProjectionSignature) {
                    resolved = cached.segments;
                }
            }
            if (resolved === null) {
                resolved = resolveMessageContentSegmentsForRendering(message, { cancelledPlaceholderText: i18n.t('chat.notifications.requestCancelled'), nowMs, timelineIndexState, timelineIndexAlreadyUpdated: timelineIndexState !== null });
                if (assistantRevision !== null && segmentProjectionSignature !== null && isAssistantMessageRole(message)) {
                    this.#segmentsCache.set(message, { assistantRevision, segmentProjectionSignature, segments: resolved });
                }
            }
            if (timelineIndexState !== null) {
                this.#assistantTimelineIndexReadyForReuse.add(message);
            }
            return resolved;
        } catch (error) {
            this.#assistantTimelineIndexReadyForReuse.delete(message);
            this.#assistantTimelineIndexCache.delete(message);
            throw error;
        }
    }

    resolveMessageReference(conversation: ConversationContract | null, messageId: string): ResolvedMessageReference {
        return resolveMessageReferenceFromConversation(conversation, messageId, (value): value is ChatMessage => this.isMessageContract(value));
    }
}

export { ChatMessageState };
