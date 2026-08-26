/* SoAI - Chat feature scroll state [frontend/assets/ts/features/chat/chatuimanager/scrollState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const CHAT_INPUT_WRAPPER_SCROLLED_CLASS = 'chat-input-wrapper--conversation-scrolled';

const getInputWrapper = (context: ChatUIManagerContext): HTMLElement | null => {
    const chatInput = context.dependencies.optionalUI(CHAT_SELECTORS.INPUT);
    if (!(chatInput instanceof HTMLElement)) {
        return null;
    }
    const wrapper = chatInput.closest('.chat-input-wrapper');
    return wrapper instanceof HTMLElement ? wrapper : null;
};

export const syncInputWrapperScrollState = (context: ChatUIManagerContext): void => {
    const wrapper = getInputWrapper(context);
    if (!wrapper) {
        return;
    }
    context.dependencies.toggleClassName(wrapper, CHAT_INPUT_WRAPPER_SCROLLED_CLASS, !context.state.autoScrollEnabled);
};
