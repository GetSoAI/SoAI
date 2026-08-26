/* SoAI - Chat page rendering [frontend/assets/ts/pages/chat/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { buildChatMainContainerMarkup } from '@pages/chat/controllers/page/markup/chatPageMainContainerMarkup.ts';
import { createChatPageMarkupContext } from '@features/chat/public.ts';
import { buildChatContainerAndSidebarMarkup } from '@pages/chat/controllers/page/markup/chatPageShellSidebarMarkup.ts';

const buildChatPageMarkup = (sanitizer: SanitizerApi, isDetached: boolean): string => {
    const context = createChatPageMarkupContext(sanitizer, isDetached);
    const sidebarHtml = buildChatContainerAndSidebarMarkup(context);
    const mainHtml = buildChatMainContainerMarkup(context);
    const contentHtml = `<div class="chat-container" data-section="chat" data-page-scope="chat"><div class="chat-content-wrapper" data-page-transition-surface="true">${sidebarHtml}${mainHtml}</div></div>`;
    return contentHtml;
};

export { buildChatPageMarkup };
