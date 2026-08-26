/* SoAI - Chat feature stream DOM cache [frontend/assets/ts/features/chat/stream/streamDomCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { AssistantEventTimelineItem, ChatMessage, ConversationMessage } from '@features/chat/ChatTypes.ts';
import { isChatMessageDomOwnedByLiveContainer } from '@features/chat/message/messageDomOwnership.ts';
import type { StreamActivityVisibleState } from '@features/chat/stream/streamActivityVisibleState.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import type { StreamingRichBlock, StreamingRichBlockProjection } from '@core/richtextrenderer/streamingBlockProjection.ts';
import { resolveHTMLElement } from '@core/dom/patching.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';

export type RenderedStreamingBlockRecord = StreamingRichBlock & {
    nodes: HTMLElement[];
};

export type StreamingElementCache = {
    conversationId: string;
    messageDomId: string;
    message: ChatMessage | null;
    messageIndex: number | null;
    messagesReference: ConversationMessage[] | null;
    messagesArea: Element | null;
    messageRoot: Element | null;
    messageText: Element | null;
    renderMode: 'streaming' | 'collapsedLoading' | null;
    lastRenderedAssistantRevision: number | null;
    activeStreamTextRunKey: string | null;
    streamText: HTMLElement | null;
    streamTextSettled: HTMLElement | null;
    streamTextTail: HTMLElement | null;
    streamSegments: HTMLElement | null;
    richTextRenderEpoch: number | null;
    richTextProjection: StreamingRichBlockProjection | null;
    renderedRichBlocks: RenderedStreamingBlockRecord[];
    renderedRichNodeCount: number;
    segmentMarkupByKey: Map<string, string> | null;
    segmentSignatureByKey: Map<string, string> | null;
    lastCollapsedLoadingHtml: string | null;
    lastAppliedActivityVisibleState: StreamActivityVisibleState | null;
    runningActivitySummaryElement: HTMLElement | null;
    textDeltaTimelineReference: AssistantEventTimelineItem[] | null;
    textDeltaTimelineScannedLength: number;
    textDeltaTimelineHasTextDelta: boolean;
};

const resolveMessagesList = (root: Element): HTMLElement | null => {
    if (root instanceof HTMLElement && root.classList.contains('chat-messages')) {
        return root;
    }
    return resolveHTMLElement(':scope > .chat-messages', root);
};

const isAssistantMessageRootMatch = (element: Element, messageDomId: string): element is HTMLElement => {
    return element instanceof HTMLElement && element.classList.contains('chat-message') && element.classList.contains('assistant') && element.getAttribute('data-id') === messageDomId;
};

const resolveDirectAssistantMessageRoot = (messagesList: HTMLElement, messageDomId: string): HTMLElement | null => {
    for (const child of Array.from(messagesList.children)) {
        if (isAssistantMessageRootMatch(child, messageDomId)) {
            return child;
        }
    }
    return null;
};

const resolveAssistantRootFromComparisonSlide = (slide: HTMLElement, messageDomId: string): HTMLElement | null => {
    const content = resolveHTMLElement(':scope > .chat-comparison-turn-slide-content', slide);
    if (content === null) {
        return null;
    }
    for (const child of Array.from(content.children)) {
        if (isAssistantMessageRootMatch(child, messageDomId)) {
            return child;
        }
    }
    return null;
};

const resolveAssistantRootFromComparisonTurn = (turn: HTMLElement, messageDomId: string): HTMLElement | null => {
    const viewport = resolveHTMLElement(':scope > .chat-comparison-turn-viewport', turn);
    if (viewport === null) {
        return null;
    }
    const track = resolveHTMLElement(':scope > .chat-comparison-turn-track', viewport);
    if (track === null) {
        return null;
    }
    for (const slide of Array.from(track.children)) {
        if (!(slide instanceof HTMLElement) || !slide.classList.contains('chat-comparison-turn-slide')) {
            continue;
        }
        const assistantRoot = resolveAssistantRootFromComparisonSlide(slide, messageDomId);
        if (assistantRoot !== null) {
            return assistantRoot;
        }
    }
    return null;
};

const resolveComparisonAssistantMessageRoot = (messagesList: HTMLElement, messageDomId: string): HTMLElement | null => {
    for (const child of Array.from(messagesList.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains('chat-comparison-turn')) {
            continue;
        }
        const assistantRoot = resolveAssistantRootFromComparisonTurn(child, messageDomId);
        if (assistantRoot !== null) {
            return assistantRoot;
        }
    }
    return null;
};

export const resolveAssistantMessageRoot = (messagesArea: Element, messageDomId: string): HTMLElement | null => {
    const messagesList = resolveMessagesList(messagesArea);
    if (!(messagesList instanceof HTMLElement)) {
        return null;
    }
    return resolveDirectAssistantMessageRoot(messagesList, messageDomId) ?? resolveComparisonAssistantMessageRoot(messagesList, messageDomId);
};

export const resolveMountedStreamingAssistantRoot = (inputArguments: { messagesArea: Element; conversationId: string; messageDomId: string; cached: StreamingElementCache | null }): HTMLElement | null => {
    const cached = inputArguments.cached;
    const cachedRoot = cached?.messageRoot;
    if (
        cached !== null &&
        cachedRoot instanceof HTMLElement &&
        cached.conversationId === inputArguments.conversationId &&
        cached.messageDomId === inputArguments.messageDomId &&
        cached.messagesArea === inputArguments.messagesArea &&
        isChatMessageDomOwnedByLiveContainer({
            liveContainer: inputArguments.messagesArea,
            messageRoot: cachedRoot,
            messageDomId: inputArguments.messageDomId
        })
    ) {
        return cachedRoot;
    }
    return resolveAssistantMessageRoot(inputArguments.messagesArea, inputArguments.messageDomId);
};

export const createStreamingElementCache = (inputArguments: { conversationId: string; messagesArea: Element; messageDomId: string }): StreamingElementCache => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        throw new Error('Streaming element cache requires a conversation id');
    }
    const messagesArea = inputArguments.messagesArea;
    const messageRoot = resolveAssistantMessageRoot(messagesArea, inputArguments.messageDomId);
    const messageText = messageRoot ? (resolveAssistantMessageParts(messageRoot)?.text ?? null) : null;
    return {
        conversationId,
        messageDomId: inputArguments.messageDomId,
        message: null,
        messageIndex: null,
        messagesReference: null,
        messagesArea,
        messageRoot,
        messageText,
        renderMode: null,
        lastRenderedAssistantRevision: null,
        activeStreamTextRunKey: null,
        streamText: null,
        streamTextSettled: null,
        streamTextTail: null,
        streamSegments: null,
        richTextRenderEpoch: null,
        richTextProjection: null,
        renderedRichBlocks: [],
        renderedRichNodeCount: 0,
        segmentMarkupByKey: null,
        segmentSignatureByKey: null,
        lastCollapsedLoadingHtml: null,
        lastAppliedActivityVisibleState: null,
        runningActivitySummaryElement: null,
        textDeltaTimelineReference: null,
        textDeltaTimelineScannedLength: 0,
        textDeltaTimelineHasTextDelta: false
    };
};

const collectMermaidContainerElements = (root: Element): HTMLElement[] => {
    const containers: HTMLElement[] = [];
    const stack: Element[] = [root];
    while (stack.length > 0) {
        const current = stack.pop();
        if (!(current instanceof HTMLElement)) {
            continue;
        }
        if (current.classList.contains('mermaid-container')) {
            containers.push(current);
        }
        const children = current.children;
        for (let index = children.length - 1; index >= 0; index -= 1) {
            const child = children[index];
            if (child instanceof Element) {
                stack.push(child);
            }
        }
    }
    return containers;
};

export const collectMermaidContainersByKey = (root: Element): Map<string, HTMLElement[]> => {
    const preserved = new Map<string, HTMLElement[]>();
    for (const container of collectMermaidContainerElements(root)) {
        const rawKey = container.getAttribute('data-mermaid-key');
        if (!isString(rawKey) || !rawKey.trim()) {
            continue;
        }
        const key = rawKey.trim();
        const queue = preserved.get(key);
        if (queue) {
            queue.push(container);
        } else {
            preserved.set(key, [container]);
        }
    }
    return preserved;
};

export const restoreMermaidContainersByKey = (root: Element, preserved: Map<string, HTMLElement[]>): void => {
    if (preserved.size === 0) {
        return;
    }
    for (const container of collectMermaidContainerElements(root)) {
        const rawKey = container.getAttribute('data-mermaid-key');
        if (!isString(rawKey) || !rawKey.trim()) {
            continue;
        }
        const key = rawKey.trim();
        const preservedQueue = preserved.get(key);
        if (!preservedQueue || preservedQueue.length === 0) {
            continue;
        }
        const preservedElement = preservedQueue.shift();
        if (!preservedElement) {
            throw new Error(`Mermaid container restore queue underflow for key ${key}`);
        }
        container.replaceWith(preservedElement);
    }
};

export const resetStreamingActivityCacheState = (cached: StreamingElementCache): void => {
    cached.lastAppliedActivityVisibleState = null;
    cached.runningActivitySummaryElement = null;
};
