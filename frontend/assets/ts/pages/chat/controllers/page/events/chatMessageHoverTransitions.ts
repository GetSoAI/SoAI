/* SoAI - Chat page message hover transitions [frontend/assets/ts/pages/chat/controllers/page/events/chatMessageHoverTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNode } from '@core/typeGuards.ts';

type ChatMessageHoverTransition = {
    messageRoot: Element;
    hovering: boolean;
};

const resolveChatMessageHoverTransition = (event: Event, hovering: boolean): ChatMessageHoverTransition | null => {
    if (!(event instanceof MouseEvent)) {
        return null;
    }
    const target = event.target;
    if (!isElementNode(target)) {
        return null;
    }
    const messageRoot = target.closest('.chat-message');
    if (!(messageRoot instanceof Element)) {
        return null;
    }
    const relatedTarget = event.relatedTarget;
    if (isElementNode(relatedTarget) && messageRoot.contains(relatedTarget)) {
        return null;
    }
    return { messageRoot, hovering };
};

export { resolveChatMessageHoverTransition };
export type { ChatMessageHoverTransition };
