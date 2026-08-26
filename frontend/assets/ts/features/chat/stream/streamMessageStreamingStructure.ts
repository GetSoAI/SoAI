/* SoAI - Chat feature stream message streaming structure [frontend/assets/ts/features/chat/stream/streamMessageStreamingStructure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resetStreamingActivityCacheState, type StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import { isStreamSegmentsElement, markStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';
import { armStreamingTextRevealLifecycle } from '@features/chat/stream/streamingTextFadeWrap.ts';

export const STREAM_TEXT_SLOT_MARKUP = '<div class="message-stream-text-block" data-stream-text="true" data-stream-text-visible="false"><div data-stream-text-settled="true"></div><div data-stream-text-tail="true"></div></div>';

export const resetTextTrackingState = (cached: StreamingElementCache): void => {
    cached.richTextRenderEpoch = null;
    cached.richTextProjection = null;
    cached.renderedRichBlocks = [];
    cached.renderedRichNodeCount = 0;
};

const resolveStreamingNodeAttachedToTarget = (target: Element, node: HTMLElement | null): HTMLElement | null => {
    if (!(node instanceof HTMLElement)) {
        return null;
    }
    return target.contains(node) ? node : null;
};

const resolveDirectStreamingTextNode = (streamSegments: HTMLElement): HTMLElement | null => {
    let streamText: HTMLElement | null = null;
    for (const child of Array.from(streamSegments.children)) {
        if (!(child instanceof HTMLElement) || child.getAttribute('data-stream-text') !== 'true') {
            continue;
        }
        if (streamText !== null) {
            throw new Error('Streaming text structure contains multiple active text slots');
        }
        streamText = child;
    }
    return streamText;
};

const resolveDirectStreamingSegmentsNode = (target: Element): HTMLElement | null => {
    let streamSegments: HTMLElement | null = null;
    const acceptCandidate = (candidate: HTMLElement): void => {
        if (streamSegments !== null) {
            throw new Error('Streaming target contains multiple segment containers');
        }
        streamSegments = candidate;
    };
    for (const child of Array.from(target.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (isStreamSegmentsElement(child)) {
            acceptCandidate(child);
            continue;
        }
        if (!child.classList.contains('message-response')) {
            continue;
        }
        for (const nestedChild of Array.from(child.children)) {
            if (nestedChild instanceof HTMLElement && isStreamSegmentsElement(nestedChild)) {
                acceptCandidate(nestedChild);
            }
        }
    }
    return streamSegments;
};

const resolveDirectMessageResponseNode = (target: Element): HTMLElement | null => {
    let response: HTMLElement | null = null;
    for (const child of Array.from(target.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains('message-response')) {
            continue;
        }
        if (response !== null) {
            throw new Error('Streaming target contains multiple response containers');
        }
        response = child;
    }
    return response;
};

const moveChildren = (source: Element, destination: Element): void => {
    while (source.firstChild !== null) {
        destination.appendChild(source.firstChild);
    }
};

const createStreamingSegmentsContainer = (target: Element): HTMLElement => {
    const container = target.ownerDocument.createElement('div');
    container.className = 'message-streaming-segments';
    markStreamSegments(container);
    return container;
};

const resetStreamingPatchState = (cached: StreamingElementCache): void => {
    resetStreamingStructureBindings(cached);
    resetStreamingActivityCacheState(cached);
    cached.lastCollapsedLoadingHtml = null;
};

const adoptStreamingSegmentsContainer = (cached: StreamingElementCache, container: HTMLElement): void => {
    resetStreamingPatchState(cached);
    cached.streamSegments = container;
    armStreamingTextRevealLifecycle(container);
};

const resolveDirectStreamTextChildren = (streamText: HTMLElement): { settled: HTMLElement; tail: HTMLElement } => {
    let settled: HTMLElement | null = null;
    let tail: HTMLElement | null = null;
    for (const child of Array.from(streamText.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (child.getAttribute('data-stream-text-settled') === 'true') {
            settled = child;
            continue;
        }
        if (child.getAttribute('data-stream-text-tail') === 'true') {
            tail = child;
        }
    }
    if (!(settled instanceof HTMLElement) || !(tail instanceof HTMLElement)) {
        throw new Error('Streaming text structure is missing settled or tail containers');
    }
    return { settled, tail };
};

const bindStreamingTextState = (cached: StreamingElementCache, streamSegments: HTMLElement): HTMLElement | null => {
    const streamText = resolveDirectStreamingTextNode(streamSegments);
    if (streamText === null) {
        cached.streamText = null;
        cached.streamTextSettled = null;
        cached.streamTextTail = null;
        return null;
    }
    if (cached.streamText instanceof HTMLElement && cached.streamText !== streamText) {
        resetTextTrackingState(cached);
        cached.lastRenderedAssistantRevision = null;
    }
    const { settled, tail } = resolveDirectStreamTextChildren(streamText);
    cached.streamText = streamText;
    cached.streamTextSettled = settled;
    cached.streamTextTail = tail;
    return streamText;
};

const resetStreamingStructureBindings = (cached: StreamingElementCache): void => {
    cached.lastRenderedAssistantRevision = null;
    cached.streamText = null;
    cached.streamTextSettled = null;
    cached.streamTextTail = null;
    resetTextTrackingState(cached);
    cached.segmentMarkupByKey = null;
    cached.segmentSignatureByKey = null;
    cached.activeStreamTextRunKey = null;
};

export const ensureStreamingSegmentsContainer = (target: Element, cached: StreamingElementCache): { streamText: HTMLElement | null; streamSegments: HTMLElement } => {
    const cachedSegments = resolveStreamingNodeAttachedToTarget(target, cached.streamSegments);
    const streamSegments = cachedSegments ?? resolveDirectStreamingSegmentsNode(target);
    if (streamSegments) {
        cached.streamSegments = streamSegments;
        armStreamingTextRevealLifecycle(streamSegments);
        return { streamText: bindStreamingTextState(cached, streamSegments), streamSegments };
    }

    const container = createStreamingSegmentsContainer(target);
    moveChildren(target, container);
    target.appendChild(container);
    adoptStreamingSegmentsContainer(cached, container);
    return { streamText: null, streamSegments: container };
};

export const ensureStreamingStructure = (target: Element, cached: StreamingElementCache): { streamText: HTMLElement | null; streamSegments: HTMLElement } => {
    const wasCollapsedLoading = cached.renderMode === 'collapsedLoading';
    const cachedSegments = wasCollapsedLoading ? null : resolveStreamingNodeAttachedToTarget(target, cached.streamSegments);
    const streamSegments = cachedSegments ?? resolveDirectStreamingSegmentsNode(target);
    if (streamSegments) {
        if (cachedSegments === null && cached.streamSegments !== streamSegments) {
            resetStreamingPatchState(cached);
        }
        cached.streamSegments = streamSegments;
        armStreamingTextRevealLifecycle(streamSegments);
        if (wasCollapsedLoading) {
            resetStreamingPatchState(cached);
            cached.streamSegments = streamSegments;
        }
        cached.renderMode = 'streaming';
        return { streamText: bindStreamingTextState(cached, streamSegments), streamSegments };
    }

    let response = resolveDirectMessageResponseNode(target);
    if (response === null) {
        response = target.ownerDocument.createElement('div');
        response.className = 'message-response';
        moveChildren(target, response);
        target.appendChild(response);
    }
    const container = createStreamingSegmentsContainer(target);

    moveChildren(response, container);
    response.appendChild(container);
    adoptStreamingSegmentsContainer(cached, container);
    cached.renderMode = 'streaming';
    return { streamText: null, streamSegments: container };
};
