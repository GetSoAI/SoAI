/* SoAI - Canonical terminal chat message hydration [frontend/assets/ts/features/chat/chatstreamservice/controller/canonicalTerminalHydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { APIError, isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { hasTerminalThinkingActivityStatusRegression } from '@features/chat/assistanteventtimeline/activityState.ts';
import { hasUnsettledTerminalAssistantActivities } from '@features/chat/assistanteventtimeline/terminalActivitySettlement.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import { resolveChatComparisonTurnMeta } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { flattenTextFragments } from '@features/chat/message/messageTextFlattening.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { findCanonicalAssistantMessage } from '@features/chat/chatstreamservice/controller/canonicalAssistantIdentity.ts';
import { isChatTurnSuperseded, type SupersedingStreamIdentityLookup } from '@features/chat/chatstreamservice/controller/turnSupersession.ts';

const RECONCILIATION_RETRY_INTERVAL_MS = 250;
const RECONCILIATION_MAX_ATTEMPTS = 60;

interface CanonicalTerminalHydrationContext {
    disposed: boolean;
    timers: ResourceTracker;
    streamStateByConversationId: Map<string, { comparisonRun: { assistantTurnTimestamp: number; variantCount: number; aborting: boolean } | null }>;
    dependencies: {
        chatStreamService: SupersedingStreamIdentityLookup & {
            syncConversationStatus(conversationId: string): Promise<ChatStreamMessageSavedReconciliation>;
            isStreaming(conversationId: string): boolean;
        };
        storageManager: { loadConversationMessages(conversationId: string, options: { force: boolean; mergeStreamingAssistants: boolean }): Promise<void> };
        conversations: Map<string, Conversation>;
        messageManager: { invalidateMessageCache(message: ChatMessage): void };
    };
}

interface CanonicalTerminalHydrationRequest {
    conversationId: string;
    assistantMessage: ChatMessage | null;
    assistantTimestamp: number;
    requireToolSettlement: boolean;
    isCurrentTerminalization: () => boolean;
}

const waitForCanonicalTerminalStatus = async (context: CanonicalTerminalHydrationContext, request: CanonicalTerminalHydrationRequest): Promise<ChatStreamMessageSavedReconciliation | null> => {
    let attempt = 0;
    while (true) {
        const reconciliation = await context.dependencies.chatStreamService.syncConversationStatus(request.conversationId);
        if (context.disposed || !request.isCurrentTerminalization()) {
            return null;
        }
        if (!context.dependencies.chatStreamService.isStreaming(request.conversationId) && reconciliation.canonicalLoad) {
            return reconciliation;
        }
        if (isChatTurnSuperseded(context.dependencies.chatStreamService, { conversationId: request.conversationId, assistantTimestamp: request.assistantTimestamp })) {
            return reconciliation;
        }
        if (attempt === RECONCILIATION_MAX_ATTEMPTS - 1) {
            throw new Error(`Chat stream terminal status remained active for ${request.conversationId}`);
        }
        await waitForCanonicalRetry(context);
        if (context.disposed || !request.isCurrentTerminalization()) {
            return null;
        }
        attempt += 1;
    }
};

const hasCompleteCanonicalComparison = (context: CanonicalTerminalHydrationContext, conversationId: string, assistantMessage: ChatMessage | null): boolean => {
    const state = context.streamStateByConversationId.get(conversationId) ?? null;
    const comparisonRun = state?.comparisonRun ?? null;
    const terminalMeta = assistantMessage === null ? null : resolveChatComparisonTurnMeta(assistantMessage);
    if (comparisonRun === null || comparisonRun.aborting || comparisonRun.variantCount <= 1 || terminalMeta === null || terminalMeta.modelVariantIndex < comparisonRun.variantCount - 1) {
        return true;
    }
    const conversation = context.dependencies.conversations.get(conversationId);
    if (!conversation) {
        return false;
    }
    const canonicalVariants = new Set<number>();
    for (const message of conversation.messages) {
        if (!isChatMessage(message) || message.role !== 'assistant') {
            continue;
        }
        const meta = resolveChatComparisonTurnMeta(message);
        if (meta !== null && meta.assistantTurnTimestamp === comparisonRun.assistantTurnTimestamp && meta.modelVariantIndex < comparisonRun.variantCount) {
            canonicalVariants.add(meta.modelVariantIndex);
        }
    }
    return canonicalVariants.size >= comparisonRun.variantCount;
};

const hasMonotonicCanonicalAssistant = (context: CanonicalTerminalHydrationContext, conversationId: string, assistantMessage: ChatMessage | null): boolean => {
    if (assistantMessage === null) {
        return true;
    }
    const canonicalAssistant = findCanonicalAssistantMessage(context.dependencies.conversations.get(conversationId), assistantMessage);
    if (canonicalAssistant === null) {
        return false;
    }
    const streamedProgress = resolveAssistantTimelineProgress(assistantMessage);
    const canonicalProgress = resolveAssistantTimelineProgress(canonicalAssistant);
    if (canonicalProgress.assistantRevision < streamedProgress.assistantRevision) {
        return false;
    }
    if (hasTerminalThinkingActivityStatusRegression(assistantMessage, canonicalAssistant)) {
        return false;
    }
    const streamedText = flattenTextFragments(assistantMessage.content).join('');
    const canonicalText = flattenTextFragments(canonicalAssistant.content).join('');
    return canonicalText.startsWith(streamedText);
};

const describeCanonicalAssistantProgress = (context: CanonicalTerminalHydrationContext, conversationId: string, assistantMessage: ChatMessage | null): string => {
    if (assistantMessage === null) {
        return 'assistant=not-required';
    }
    const canonicalAssistant = findCanonicalAssistantMessage(context.dependencies.conversations.get(conversationId), assistantMessage);
    if (canonicalAssistant === null) {
        return `assistant=missing,turn=${String(assistantMessage.assistantTurnAtMs)},variant=${String(assistantMessage.modelVariantIndex)}`;
    }
    const streamedProgress = resolveAssistantTimelineProgress(assistantMessage);
    const canonicalProgress = resolveAssistantTimelineProgress(canonicalAssistant);
    const streamedText = flattenTextFragments(assistantMessage.content).join('');
    const canonicalText = flattenTextFragments(canonicalAssistant.content).join('');
    return `assistant=present,timeline=${String(canonicalProgress.entryCount)}/${String(streamedProgress.entryCount)},revision=${String(canonicalProgress.assistantRevision)}/${String(streamedProgress.assistantRevision)},text=${String(canonicalText.length)}/${String(streamedText.length)},textPrefix=${String(canonicalText.startsWith(streamedText))}`;
};

const isRetryableCanonicalReadError = (error: Error): boolean => {
    if (isNetworkError(error) || isRequestTimeoutError(error)) return true;
    return error instanceof APIError && (error.status === 408 || error.status === 425 || error.status === 429 || error.status >= 500);
};

const waitForCanonicalRetry = async (context: CanonicalTerminalHydrationContext, error?: Error): Promise<void> => {
    const retryAfterMs = error instanceof APIError && typeof error.retryAfterSeconds === 'number' && Number.isFinite(error.retryAfterSeconds) ? Math.max(0, error.retryAfterSeconds * 1000) : 0;
    await context.timers.waitForTimeout(Math.max(RECONCILIATION_RETRY_INTERVAL_MS, retryAfterMs));
};

const hasSettledCanonicalTools = (context: CanonicalTerminalHydrationContext, conversationId: string, assistantMessage: ChatMessage | null, requireToolSettlement: boolean): boolean => {
    if (!requireToolSettlement || assistantMessage === null) {
        return true;
    }
    const canonicalAssistant = findCanonicalAssistantMessage(context.dependencies.conversations.get(conversationId), assistantMessage);
    return canonicalAssistant === null || !hasUnsettledTerminalAssistantActivities(canonicalAssistant);
};

const loadCanonicalTerminalMessages = async (context: CanonicalTerminalHydrationContext, request: CanonicalTerminalHydrationRequest): Promise<boolean> => {
    const conversationId = request.conversationId;
    const assistantMessage = request.assistantMessage;
    const requireToolSettlement = request.requireToolSettlement;
    let attempt = 0;
    while (true) {
        try {
            await context.dependencies.storageManager.loadConversationMessages(conversationId, { force: true, mergeStreamingAssistants: false });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isRetryableCanonicalReadError(runtimeError) || attempt === RECONCILIATION_MAX_ATTEMPTS - 1) throw runtimeError;
            await waitForCanonicalRetry(context, runtimeError);
            if (context.disposed || !request.isCurrentTerminalization()) return false;
            attempt += 1;
            continue;
        }
        const conversation = context.dependencies.conversations.get(conversationId);
        for (const message of conversation?.messages ?? []) {
            if (isChatMessage(message) && message.role === 'assistant') {
                context.dependencies.messageManager.invalidateMessageCache(message);
            }
        }
        if (context.disposed || !request.isCurrentTerminalization()) {
            return false;
        }
        const canonicalProgressDescription = describeCanonicalAssistantProgress(context, conversationId, assistantMessage);
        const hasMonotonicAssistant = hasMonotonicCanonicalAssistant(context, conversationId, assistantMessage);
        const hasCompleteComparison = hasCompleteCanonicalComparison(context, conversationId, assistantMessage);
        const hasSettledTools = hasSettledCanonicalTools(context, conversationId, assistantMessage, requireToolSettlement);
        if (hasMonotonicAssistant && hasCompleteComparison && hasSettledTools) {
            return true;
        }
        if (attempt === RECONCILIATION_MAX_ATTEMPTS - 1) {
            throw new Error(`Canonical terminal messages remained incomplete for ${conversationId}: ${canonicalProgressDescription},comparisonComplete=${String(hasCompleteComparison)},toolsSettled=${String(hasSettledTools)}`);
        }
        await waitForCanonicalRetry(context);
        if (context.disposed || !request.isCurrentTerminalization()) {
            return false;
        }
        attempt += 1;
    }
};

const reconcileCanonicalTerminalMessages = async (context: CanonicalTerminalHydrationContext, request: CanonicalTerminalHydrationRequest): Promise<boolean> => {
    const reconciliation = await waitForCanonicalTerminalStatus(context, request);
    if (reconciliation === null || context.disposed || !request.isCurrentTerminalization()) {
        return false;
    }
    return await loadCanonicalTerminalMessages(context, request);
};

export { reconcileCanonicalTerminalMessages };
export type { CanonicalTerminalHydrationContext, CanonicalTerminalHydrationRequest };
