/* SoAI - Operation-local canonical message-body search projection [frontend/assets/ts/features/chat/message/searchTextProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createInertHtmlParser } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { visitSearchTextBlocks, type SearchTextBlock } from '@core/search/domTextIndex.ts';
import type { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveMessageContentSegmentsForRendering } from '@features/chat/message/messageSegmentsResolution.ts';
import { chatSearchTextTraversalPolicy, isSearchableChatMessage } from '@features/chat/message/searchTextPolicy.ts';

type MessageSearchTextProjection = (message: ChatMessage, budget: SearchWorkBudget, visitBlock: (block: SearchTextBlock) => Promise<boolean>) => Promise<boolean>;
type MessageSearchTextRenderer = (content: string, role: 'user' | 'assistant', signal: AbortSignal | null) => Promise<string>;

const createMessageSearchProjection = (renderText: MessageSearchTextRenderer, documentRef: Document): MessageSearchTextProjection => {
    const parseMarkup = createInertHtmlParser(documentRef);
    return async (message, budget, visitBlock) => {
        await budget.checkpoint();
        if (!isSearchableChatMessage(message)) return true;
        const segments = resolveMessageContentSegmentsForRendering(message, { cancelledPlaceholderText: i18n.t('chat.notifications.requestCancelled'), nowMs: serverEpochMs() });
        for (const segment of segments) {
            if (segment.type !== 'text') continue;
            await budget.checkpoint();
            const markup = await renderText(segment.text, message.role === 'assistant' ? 'assistant' : 'user', budget.signal);
            await budget.checkpoint();
            const fragment = await parseMarkup(markup, () => budget.checkpoint());
            if (!(await visitSearchTextBlocks(fragment, chatSearchTextTraversalPolicy, budget, visitBlock, false))) return false;
        }
        return true;
    };
};

export { createMessageSearchProjection };
export type { MessageSearchTextProjection, MessageSearchTextRenderer };
