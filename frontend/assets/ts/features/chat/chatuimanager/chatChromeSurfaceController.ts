/* SoAI - Chat chrome auto-hide surface controller [frontend/assets/ts/features/chat/chatuimanager/chatChromeSurfaceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { applyChatChromeSurfaceVisibilityScroll, beginChatChromeSurfaceHoverReveal, CHAT_CHROME_HOVER_REVEAL_HEIGHT_PX, createChatChromeSurfaceVisibilityState, dismissChatChromeSurfaceHoverReveal, endChatChromeSurfaceHoverSuppression, holdChatChromeSurfaceHoverReveal, releaseChatChromeSurfaceHoverReveal, type ChatChromeSurfaceVisibilityState } from '@features/chat/chatuimanager/chatChromeVisibilityPolicy.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

export type ChatChromeSurfaceConfig = {
    revealEdge: 'top' | 'bottom';
    resolveElement: () => HTMLElement | null;
    resolveInteractionElements: (element: HTMLElement) => readonly HTMLElement[];
    resolveRevealBounds: (element: HTMLElement) => GeometryBox | null;
    isPinned: (element: HTMLElement) => boolean;
    isTemporaryHideExempt: (shown: boolean) => boolean;
    isRevealBlocked: () => boolean;
    isPointerTargetIgnored: (target: EventTarget | null) => boolean;
    project: (element: HTMLElement, visible: boolean) => void;
};

export type ChatChromeSurfaceController = {
    observeDelta: (delta: number, hideableDistance: number) => void;
    sync: (hideableDistance: number | null) => void;
    handlePointerMove: (event: Event, allowReveal?: boolean) => void;
    commit: () => void;
    reset: () => void;
    isShown: () => boolean;
    setTemporarilyHidden: (hidden: boolean) => void;
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
    let suspendedVisibility: { state: ChatChromeSurfaceVisibilityState; remainingDismissDelay: number | null } | null = null;
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
        state = next;
        if (pinned) {
            if (suspendedVisibility === null) state = createChatChromeSurfaceVisibilityState();
            else if (state.hoverActive) state = holdChatChromeSurfaceHoverReveal(state);
        }
        if (state.hoverDismissAt !== previousDismissAt) scheduleDismissTimer();
        if (element === null) return;
        shown = (suspendedVisibility === null && pinned) || (!config.isRevealBlocked() && (state.visible || (suspendedVisibility !== null && config.isTemporaryHideExempt(shown))));
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

    const isInteractionTarget = (target: EventTarget | null): boolean => {
        const element = config.resolveElement();
        return element !== null && target instanceof Node && !config.isPointerTargetIgnored(target) && config.resolveInteractionElements(element).some((surface) => surface.contains(target));
    };

    const handlePointerMove = (event: Event, allowReveal = true): void => {
        const permanentlyVisible = state.visible && !state.hoverActive && !state.hoverSuppressed;
        if (!isMousePointer(event) || permanentlyVisible) return;
        const withinRevealStrip = isWithinRevealStrip(event);
        if (state.hoverSuppressed) {
            if (!withinRevealStrip) apply(endChatChromeSurfaceHoverSuppression(state));
            return;
        }
        const ignored = config.isPointerTargetIgnored(event.target);
        if (allowReveal && (suspendedVisibility === null || event.buttons === 0) && !ignored && withinRevealStrip && !config.isRevealBlocked()) apply(beginChatChromeSurfaceHoverReveal(state, Date.now()));
        if (!state.hoverActive) return;
        const element = config.resolveElement();
        const point = measureLayoutPoint(event, documentRef);
        const withinInteractionSurface =
            !ignored &&
            element !== null &&
            config.resolveInteractionElements(element).some((surface) => {
                const bounds = measureLayoutBox(surface);
                return bounds.height > 0 && point.x >= bounds.left && point.x <= bounds.right && point.y >= bounds.top && point.y <= bounds.bottom;
            });
        apply(withinInteractionSurface ? holdChatChromeSurfaceHoverReveal(state) : releaseChatChromeSurfaceHoverReveal(state, Date.now()));
    };

    const element = config.resolveElement();
    for (const surface of element === null ? [] : config.resolveInteractionElements(element)) {
        disposers.push(
            dependencies.runtime.on(
                surface,
                'pointerenter',
                (event) => {
                    if (isMousePointer(event) && !config.isPointerTargetIgnored(event.target)) apply(holdChatChromeSurfaceHoverReveal(state));
                },
                { passive: true }
            ),
            dependencies.runtime.on(
                surface,
                'pointerleave',
                (event) => {
                    if (isMousePointer(event)) apply(isInteractionTarget(event.relatedTarget) ? holdChatChromeSurfaceHoverReveal(state) : releaseChatChromeSurfaceHoverReveal(state, Date.now()));
                },
                { passive: true }
            )
        );
    }

    return {
        observeDelta: (delta, hideableDistance) => apply(suspendedVisibility === null ? applyChatChromeSurfaceVisibilityScroll(state, { delta, hideableDistance }) : state),
        sync: (hideableDistance) => apply(suspendedVisibility !== null || state.visible || hideableDistance === null ? state : applyChatChromeSurfaceVisibilityScroll(state, { delta: 0, hideableDistance })),
        handlePointerMove,
        commit: () => apply(state),
        reset: () => {
            if (suspendedVisibility !== null) {
                suspendedVisibility = { state: createChatChromeSurfaceVisibilityState(), remainingDismissDelay: null };
                apply({ ...createChatChromeSurfaceVisibilityState(), visible: false });
            } else {
                apply(createChatChromeSurfaceVisibilityState());
            }
        },
        isShown: () => shown,
        setTemporarilyHidden: (hidden) => {
            if ((suspendedVisibility !== null) === hidden) {
                if (hidden) apply({ ...createChatChromeSurfaceVisibilityState(), visible: false });
                return;
            }
            if (hidden) {
                suspendedVisibility = { state, remainingDismissDelay: state.hoverDismissAt === null ? null : Math.max(0, state.hoverDismissAt - Date.now()) };
                clearDismissTimer();
                apply({ ...createChatChromeSurfaceVisibilityState(), visible: false });
            } else if (suspendedVisibility !== null) {
                const restored = suspendedVisibility;
                suspendedVisibility = null;
                apply(config.isTemporaryHideExempt(shown) ? createChatChromeSurfaceVisibilityState() : { ...restored.state, hoverDismissAt: restored.remainingDismissDelay === null ? null : Date.now() + restored.remainingDismissDelay });
            }
        },
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
