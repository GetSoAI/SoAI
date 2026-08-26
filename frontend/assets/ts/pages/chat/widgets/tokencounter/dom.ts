/* SoAI - Chat page token counter DOM contracts [frontend/assets/ts/pages/chat/widgets/tokencounter/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';

const requireChatTokenCounterLabel = (button: HTMLButtonElement): HTMLElement => {
    const label = dom.resolve('.chat-token-counter-label', button);
    if (!label) {
        throw new Error('Chat token counter button requires .chat-token-counter-label');
    }
    return narrowHTMLElement(label, 'Chat token counter label');
};

export { requireChatTokenCounterLabel };
