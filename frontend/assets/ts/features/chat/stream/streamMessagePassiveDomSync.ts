/* SoAI - Chat feature stream message passive DOM sync [frontend/assets/ts/features/chat/stream/streamMessagePassiveDomSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { resolveStatusPreviewDomStateFromMessage } from '@features/chat/assistanteventtimeline/statusPreviewState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE, syncRunningActivitySummaryElement } from '@features/chat/message/messageRunningActivitySummaryMarkup.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { reconcileStreamingSpinnerStatusSubtree } from '@features/chat/stream/streamMessageSpinnerStatusRuntime.ts';
import type { RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';

const syncStreamingStatusPreviewAttributes = (message: ChatMessage, messageTextRoot: Element, streaming: boolean): boolean => {
    const messageRoot = messageTextRoot.closest('.chat-message');
    if (!(messageRoot instanceof HTMLElement)) {
        return false;
    }
    const actions = resolveAssistantMessageParts(messageRoot)?.actions ?? null;
    if (!(actions instanceof HTMLElement)) {
        return false;
    }
    const previewState = resolveStatusPreviewDomStateFromMessage(message);
    const nextStreaming = streaming ? 'true' : 'false';
    const nextHasPreview = streaming && previewState.hasPreview ? 'true' : 'false';
    const nextText = streaming ? previewState.text : '';
    const nextCooldownMs = streaming && previewState.hasPreview ? String(previewState.cooldownMs) : '0';
    const streamingChanged = actions.getAttribute('data-message-streaming') !== nextStreaming;
    const hasPreviewChanged = actions.getAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE) !== nextHasPreview;
    const textChanged = actions.getAttribute(STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE) !== nextText;
    const cooldownChanged = actions.getAttribute(STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE) !== nextCooldownMs;
    if (streamingChanged) {
        actions.setAttribute('data-message-streaming', nextStreaming);
    }
    if (hasPreviewChanged) {
        actions.setAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, nextHasPreview);
    }
    if (textChanged) {
        actions.setAttribute(STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE, nextText);
    }
    if (cooldownChanged) {
        actions.setAttribute(STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, nextCooldownMs);
    }
    const changed = streamingChanged || hasPreviewChanged || textChanged || cooldownChanged;
    if (changed) {
        reconcileStreamingSpinnerStatusSubtree(messageRoot);
    }
    return changed;
};

const resolveCachedRunningActivitySummaryElement = (messageRoot: HTMLElement, cached: StreamingElementCache | null | undefined): HTMLElement | null => {
    const summary = cached?.runningActivitySummaryElement ?? null;
    if (!(summary instanceof HTMLElement) || !summary.isConnected || !messageRoot.contains(summary)) {
        if (cached) {
            cached.runningActivitySummaryElement = null;
        }
        return null;
    }
    return summary;
};

const resolveRunningActivitySummaryElement = (messageRoot: HTMLElement, cached: StreamingElementCache | null | undefined): HTMLElement | null => {
    const cachedSummary = resolveCachedRunningActivitySummaryElement(messageRoot, cached);
    if (cachedSummary !== null) {
        return cachedSummary;
    }
    const actions = resolveAssistantMessageParts(messageRoot)?.actions ?? null;
    if (!(actions instanceof HTMLElement)) {
        return null;
    }
    const summary = dom.resolve(`[${RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE}="true"]`, actions);
    if (!(summary instanceof HTMLElement)) {
        return null;
    }
    if (cached) {
        cached.runningActivitySummaryElement = summary;
    }
    return summary;
};

const syncRunningActivitySummaryForMessageRoot = (summary: RunningActivitySummary, messageRoot: HTMLElement, cached?: StreamingElementCache | null): boolean => {
    const summaryElement = resolveRunningActivitySummaryElement(messageRoot, cached);
    if (!(summaryElement instanceof HTMLElement)) {
        return false;
    }
    return syncRunningActivitySummaryElement(summaryElement, summary);
};

const syncRunningActivitySummaryForMessageTextRoot = (summary: RunningActivitySummary, messageTextRoot: Element, cached?: StreamingElementCache | null): boolean => {
    const cachedRoot = cached?.messageRoot;
    const messageRoot = cachedRoot instanceof HTMLElement && cachedRoot.contains(messageTextRoot) ? cachedRoot : messageTextRoot.closest('.chat-message');
    if (!(messageRoot instanceof HTMLElement)) {
        return false;
    }
    return syncRunningActivitySummaryForMessageRoot(summary, messageRoot, cached);
};

export { syncRunningActivitySummaryForMessageRoot, syncRunningActivitySummaryForMessageTextRoot, syncStreamingStatusPreviewAttributes };
