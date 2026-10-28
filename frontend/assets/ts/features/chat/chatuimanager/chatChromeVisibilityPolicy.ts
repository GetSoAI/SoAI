/* SoAI - Chat chrome auto-hide transition policy [frontend/assets/ts/features/chat/chatuimanager/chatChromeVisibilityPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type ChatChromeSurfaceVisibilityState = {
    visible: boolean;
    upwardDistance: number;
    downwardDistance: number;
    hoverActive: boolean;
    hoverDismissAt: number | null;
    hoverSuppressed: boolean;
};

export const CHAT_CHROME_AUTO_HIDE_DISTANCE_PX = 24;
export const CHAT_CHROME_HOVER_DISMISS_DELAY_MS = 10000;
export const CHAT_CHROME_HOVER_REVEAL_HEIGHT_PX = 24;

export const createChatChromeSurfaceVisibilityState = (): ChatChromeSurfaceVisibilityState => ({ visible: true, upwardDistance: 0, downwardDistance: 0, hoverActive: false, hoverDismissAt: null, hoverSuppressed: false });

export const applyChatChromeSurfaceVisibilityScroll = (state: ChatChromeSurfaceVisibilityState, inputArguments: { delta: number; hideableDistance: number }): ChatChromeSurfaceVisibilityState => {
    const { delta, hideableDistance } = inputArguments;
    if (hideableDistance <= 0) return createChatChromeSurfaceVisibilityState();
    if (delta < 0) {
        const upwardDistance = state.upwardDistance + Math.min(-delta, hideableDistance);
        if (upwardDistance < CHAT_CHROME_AUTO_HIDE_DISTANCE_PX) return { ...state, upwardDistance, downwardDistance: 0 };
        return { ...state, visible: false, upwardDistance: 0, downwardDistance: 0, hoverActive: false, hoverDismissAt: null };
    }
    if (delta > 0) {
        const downwardDistance = state.downwardDistance + delta;
        if (downwardDistance < CHAT_CHROME_AUTO_HIDE_DISTANCE_PX) return { ...state, upwardDistance: 0, downwardDistance };
        return createChatChromeSurfaceVisibilityState();
    }
    return state;
};

export const beginChatChromeSurfaceHoverReveal = (state: ChatChromeSurfaceVisibilityState, now: number): ChatChromeSurfaceVisibilityState => (state.visible || state.hoverSuppressed ? state : { ...state, visible: true, upwardDistance: 0, downwardDistance: 0, hoverActive: true, hoverDismissAt: now + CHAT_CHROME_HOVER_DISMISS_DELAY_MS });

export const holdChatChromeSurfaceHoverReveal = (state: ChatChromeSurfaceVisibilityState): ChatChromeSurfaceVisibilityState => (state.hoverActive && state.hoverDismissAt !== null ? { ...state, hoverDismissAt: null } : state);

export const releaseChatChromeSurfaceHoverReveal = (state: ChatChromeSurfaceVisibilityState, now: number): ChatChromeSurfaceVisibilityState => (state.hoverActive && state.hoverDismissAt === null ? { ...state, hoverDismissAt: now + CHAT_CHROME_HOVER_DISMISS_DELAY_MS } : state);

export const dismissChatChromeSurfaceHoverReveal = (state: ChatChromeSurfaceVisibilityState, now: number): ChatChromeSurfaceVisibilityState => (state.hoverActive && state.hoverDismissAt !== null && now >= state.hoverDismissAt ? { ...state, visible: false, upwardDistance: 0, downwardDistance: 0, hoverActive: false, hoverDismissAt: null, hoverSuppressed: true } : state);

export const endChatChromeSurfaceHoverSuppression = (state: ChatChromeSurfaceVisibilityState): ChatChromeSurfaceVisibilityState => (state.hoverSuppressed ? { ...state, hoverSuppressed: false } : state);
