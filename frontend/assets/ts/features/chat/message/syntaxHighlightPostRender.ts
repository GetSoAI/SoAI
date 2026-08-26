/* SoAI - Chat feature syntax highlight post render [frontend/assets/ts/features/chat/message/syntaxHighlightPostRender.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { CHAT_CODE_BLOCK_SELECTOR } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

const highlightStableChatCodeBlocks = (container: HTMLElement, syntaxHighlighter: SyntaxHighlighter, streamingTailSelector: string): void => {
    const blocks = dom.resolveAll(CHAT_CODE_BLOCK_SELECTOR, container);
    if (blocks.length === 0) {
        return;
    }
    for (const block of blocks) {
        if (!(block instanceof HTMLPreElement)) {
            continue;
        }
        if (block.closest(streamingTailSelector) !== null) {
            continue;
        }
        syntaxHighlighter.highlightElement(block);
    }
};

export { highlightStableChatCodeBlocks };
