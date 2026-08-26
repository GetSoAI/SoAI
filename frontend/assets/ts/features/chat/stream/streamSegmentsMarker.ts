/* SoAI - Chat feature stream segments marker [frontend/assets/ts/features/chat/stream/streamSegmentsMarker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

const STREAM_SEGMENTS_ATTRIBUTE = 'data-stream-segments';
const STREAM_SEGMENTS_ATTRIBUTE_VALUE = 'true';
const STREAM_SEGMENTS_SELECTOR = `[${STREAM_SEGMENTS_ATTRIBUTE}="${STREAM_SEGMENTS_ATTRIBUTE_VALUE}"]`;

const markStreamSegments = (element: Element): void => {
    element.setAttribute(STREAM_SEGMENTS_ATTRIBUTE, STREAM_SEGMENTS_ATTRIBUTE_VALUE);
};

const isStreamSegmentsElement = (element: Element): boolean => {
    return element.getAttribute(STREAM_SEGMENTS_ATTRIBUTE) === STREAM_SEGMENTS_ATTRIBUTE_VALUE;
};

const resolveStreamSegments = (root: Element): HTMLElement | null => {
    const node = dom.resolve(STREAM_SEGMENTS_SELECTOR, root);
    return node instanceof HTMLElement ? node : null;
};

const resolveDirectStreamSegments = (root: Element): HTMLElement | null => {
    let streamSegments: HTMLElement | null = null;
    for (const child of Array.from(root.children)) {
        if (!(child instanceof HTMLElement) || !isStreamSegmentsElement(child)) {
            continue;
        }
        if (streamSegments !== null) {
            throw new Error('Streaming container owner contains multiple direct segment containers');
        }
        streamSegments = child;
    }
    return streamSegments;
};

const hasStreamSegments = (root: Element): boolean => {
    return resolveStreamSegments(root) !== null;
};

export { STREAM_SEGMENTS_ATTRIBUTE, STREAM_SEGMENTS_SELECTOR, hasStreamSegments, isStreamSegmentsElement, markStreamSegments, resolveDirectStreamSegments, resolveStreamSegments };
