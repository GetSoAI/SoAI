/* SoAI - Chat chrome auto-hide surface controller [frontend/assets/ts/features/chat/chatuimanager/chatChromeSurfaceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutPoint, measureLayoutViewport, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { applyChatChromeSurfaceVisibilityScroll, beginChatChromeSurfaceHoverReveal, CHAT_CHROME_HOVER_REVEAL_HEIGHT_PX, createChatChromeSurfaceVisibilityState, dismissChatChromeSurfaceHoverReveal, endChatChromeSurfaceHoverSuppression, holdChatChromeSurfaceHoverReveal, releaseChatChromeSurfaceHoverReveal, type ChatChromeSurfaceVisibilityState } from '@features/chat/chatuimanager/chatChromeVisibilityPolicy.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

export type ChatChromeSurfaceConfig = {
    revealEdge: 'top' | 'bottom';
    resolveElement: () => HTMLElement | null;
    resolveRevealBounds: (element: HTMLElement) => GeometryBox | null;
    isPinned: (element: HTMLElement) => boolean;
    isRevealBlocked: () => boolean;
    isPointerTargetIgnored: (target: EventTarget | null) => boolean;
    project: (element: HTMLElement, visible: boolean) => void;
};

export type ChatChromeSurfaceController = {
    observeDelta: (delta: number, hideableDistance: number) => void;
    sync: (hideableDistance: number | null) => void;
    handlePointerMove: (event: Event) => void;
    commit: () => void;
    reset: () => void;
    isShown: () => boolean;
    addDisposer: (dispose: () => void) => void;
    dispose: () => void;
};

const isMousePointer = (event: Event): event is PointerEvent => event instanceof PointerEvent && event.pointerType === 'mouse';

export const createChatChromeSurfaceController = (context: ChatUIManagerContext, inputArguments: { config: ChatChromeSurfaceConfig; isGlobalPinned: () => boolean }): ChatChromeSurfaceController => {
    const { config, isGlobalPinned } = inputArguments;
    const dependencies = context.dependencies;
    const documentRef = dependencies.dom.getDocument();
    let state: ChatChromeSurfaceVisibilityState = createChatChromeSurfaceVisibilityState();
    let dismissTimer: number | null = null;
    let shown = true;
    const disposers: Array<() => void> = [];

    const clearDismissTimer = (): void => {
        if (dismissTimer === null) return;
        dependencies.runtime.clearTimer(dismissTimer);
        dismissTimer = null;
    };

    const scheduleDismissTimer = (): void => {
        clearDismissTimer();
        const dismissAt = state.hoverDismissAt;
        if (dismissAt === null) return;
        dismissTimer = dependencies.runtime.setTimer(
            () => {
                dismissTimer = null;
                apply(dismissChatChromeSurfaceHoverReveal(state, Date.now()));
            },
            Math.max(0, dismissAt - Date.now())
        );
    };

    const apply = (next: ChatChromeSurfaceVisibilityState): void => {
        const previousDismissAt = state.hoverDismissAt;
        const element = config.resolveElement();
        const pinned = isGlobalPinned() || (element !== null && config.isPinned(element));
        state = pinned ? createChatChromeSurfaceVisibilityState() : next;
        if (state.hoverDismissAt !== previousDismissAt) scheduleDismissTimer();
        if (element === null) return;
        shown = pinned || (!config.isRevealBlocked() && state.visible);
        config.project(element, shown);
    };

    const isWithinRevealStrip = (event: PointerEvent): boolean => {
        const element = config.resolveElement();
        const bounds = element === null ? null : config.resolveRevealBounds(element);
        if (bounds === null) return false;
        const point = measureLayoutPoint(event, documentRef);
        if (point.x < bounds.left || point.x > bounds.right) return false;
        if (config.revealEdge === 'top') return point.y >= bounds.top && point.y <= bounds.top + CHAT_CHROME_HOVER_REVEAL_HEIGHT_PX;
        return point.y >= bounds.bottom - CHAT_CHROME_HOVER_REVEAL_HEIGHT_PX && point.y <= measureLayoutViewport(documentRef).height;
    };

    const handlePointerMove = (event: Event): void => {
        if (!isMousePointer(event) || (state.visible && !state.hoverSuppressed) || config.isPointerTargetIgnored(event.target)) return;
        const withinRevealStrip = isWithinRevealStrip(event);
        if (state.hoverSuppressed) {
            if (!withinRevealStrip) apply(endChatChromeSurfaceHoverSuppression(state));
            return;
        }
        if (withinRevealStrip && !config.isRevealBlocked()) apply(beginChatChromeSurfaceHoverReveal(state, Date.now()));
    };

    const element = config.resolveElement();
    if (element !== null) {
        disposers.push(
            dependencies.runtime.on(
                element,
                'pointerenter',
                (event) => {
                    if (isMousePointer(event)) apply(holdChatChromeSurfaceHoverReveal(state));
                },
                { passive: true }
            ),
            dependencies.runtime.on(
                element,
                'pointerleave',
                (event) => {
                    if (isMousePointer(event)) apply(releaseChatChromeSurfaceHoverReveal(state, Date.now()));
                },
                { passive: true }
            )
        );
    }

    return {
        observeDelta: (delta, hideableDistance) => apply(applyChatChromeSurfaceVisibilityScroll(state, { delta, hideableDistance })),
        sync: (hideableDistance) => apply(state.visible || hideableDistance === null ? state : applyChatChromeSurfaceVisibilityScroll(state, { delta: 0, hideableDistance })),
        handlePointerMove,
        commit: () => apply(state),
        reset: () => apply(createChatChromeSurfaceVisibilityState()),
        isShown: () => shown,
        addDisposer: (dispose) => {
            disposers.push(dispose);
        },
        dispose: () => {
            clearDismissTimer();
            for (const dispose of disposers.splice(0)) dispose();
            const current = config.resolveElement();
            if (current !== null) config.project(current, true);
            shown = true;
        }
    };
};
