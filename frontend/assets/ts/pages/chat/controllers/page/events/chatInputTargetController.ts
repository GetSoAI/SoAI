/* SoAI - Chat page input target controller [frontend/assets/ts/pages/chat/controllers/page/events/chatInputTargetController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const resolveChatInputTarget = (target: EventTarget | null): HTMLTextAreaElement | null => {
    if (!(target instanceof Element) || !target.matches('.chat-input')) {
        return null;
    }
    if (!(target instanceof HTMLTextAreaElement)) {
        throw new TypeError('Chat input target must be a textarea');
    }
    return target;
};

export { resolveChatInputTarget };
