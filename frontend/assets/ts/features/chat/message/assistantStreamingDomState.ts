/* SoAI - Assistant streaming DOM state detection [frontend/assets/ts/features/chat/message/assistantStreamingDomState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { STREAM_SEGMENTS_SELECTOR } from '@features/chat/stream/streamSegmentsMarker.ts';

const ASSISTANT_STREAM_TEXT_SELECTOR = '[data-stream-text="true"]';

const hasStreamingAssistantDom = (root: HTMLElement): boolean => dom.resolve([STREAM_SEGMENTS_SELECTOR, ASSISTANT_STREAM_TEXT_SELECTOR, '[data-stream-text-settled="true"]', '[data-stream-text-tail="true"]'].join(','), root) !== null;

const collectCanonicalStreamingTextChildNodes = (streamText: HTMLElement): ChildNode[] => {
    const nodes: ChildNode[] = [];
    for (const child of Array.from(streamText.childNodes)) {
        if (child instanceof HTMLElement && (child.getAttribute('data-stream-text-settled') === 'true' || child.getAttribute('data-stream-text-tail') === 'true')) {
            nodes.push(...Array.from(child.childNodes));
            continue;
        }
        nodes.push(child);
    }
    return nodes;
};

export { ASSISTANT_STREAM_TEXT_SELECTOR, collectCanonicalStreamingTextChildNodes, hasStreamingAssistantDom };
