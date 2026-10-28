/* SoAI - Chat chrome auto-hide presentation runtime [frontend/assets/ts/features/chat/chatuimanager/chatChromeVisibilityRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureViewportPoint } from '@core/layout/elementGeometry.ts';

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { setupChatComposerChromeSurface } from '@features/chat/chatuimanager/chatComposerChromeSurface.ts';
import { setupChatConversationHeaderChromeSurface } from '@features/chat/chatuimanager/chatConversationHeaderChromeSurface.ts';
import { isConversationScrollRestoreActive } from '@features/chat/chatuimanager/conversationScrollRestoration.ts';
import { getElement, isAnyElementShown } from '@features/chat/chatuimanager/dom.ts';
import { syncInputWrapperScrollState } from '@features/chat/chatuimanager/scrollState.ts';
import type { ChatChromeVisibilityRuntime, ChatUIManagerContext, ElementSelectorKey } from '@features/chat/chatuimanager/types.ts';
import { consumeMainTimelineProgrammaticScrollOffset } from '@features/chat/mainTimelineScroll.ts';

const ATTENTION_PREVIEW_KEYS: readonly ElementSelectorKey[] = ['toolApprovalPreview', 'askUserPreview', 'secretPromptPreview'];

const isAdvancedScrollPreviewEngaged = (context: ChatUIManagerContext, target: EventTarget | null): boolean => {
    const overlay = context.state.advancedScrollPreviewOverlay;
    if (overlay === null) return false;
    return overlay.classList.contains(CSS_CLASSES.HOVER) || (target instanceof Node && overlay.contains(target));
};

export const setupChatChromeVisibilityRuntime = (context: ChatUIManagerContext): ChatChromeVisibilityRuntime => {
    const dependencies = context.dependencies;
    const documentRef = dependencies.dom.getDocument();
    let lastScrollTop: number | null = null;
    let lastMousePointerPoint: { x: number; y: number } | null = null;

    const isGlobalPinned = (): boolean => context.state.activeConversationTransitionId !== null || isAnyElementShown(context, ATTENTION_PREVIEW_KEYS);

    const surfaces = [setupChatConversationHeaderChromeSurface(context, isGlobalPinned), setupChatComposerChromeSurface(context, isGlobalPinned)];

    const resolveHideableDistance = (messagesArea: HTMLElement): number => {
        if (dependencies.session.getCurrentConversation()?.history?.hasNewer === true) return Number.POSITIVE_INFINITY;
        return messagesArea.scrollHeight - messagesArea.scrollTop - messagesArea.clientHeight * 2;
    };

    const observeScroll = (): void => {
        const messagesArea = getElement(context, 'messagesArea');
        if (messagesArea === null) return;
        const programmaticOffset = consumeMainTimelineProgrammaticScrollOffset(messagesArea);
        const scrollTop = messagesArea.scrollTop;
        const delta = lastScrollTop === null || isConversationScrollRestoreActive(context) ? 0 : scrollTop - lastScrollTop - programmaticOffset;
        lastScrollTop = scrollTop;
        const hideableDistance = resolveHideableDistance(messagesArea);
        for (const surface of surfaces) surface.observeDelta(delta, hideableDistance);
    };

    const sync = (): void => {
        syncInputWrapperScrollState(context);
        const messagesArea = getElement(context, 'messagesArea');
        const hideableDistance = messagesArea === null ? null : resolveHideableDistance(messagesArea);
        for (const surface of surfaces) surface.sync(hideableDistance);
    };

    const disposePointerMove = dependencies.runtime.on(
        documentRef,
        'pointermove',
        (event) => {
            if (!(event instanceof PointerEvent) || event.pointerType !== 'mouse') return;
            const point = measureViewportPoint(event);
            const pointerMoved = lastMousePointerPoint === null || point.x !== lastMousePointerPoint.x || point.y !== lastMousePointerPoint.y;
            lastMousePointerPoint = point;
            const allowReveal = pointerMoved && !isAdvancedScrollPreviewEngaged(context, event.target);
            for (const surface of surfaces) surface.handlePointerMove(event, allowReveal);
        },
        { passive: true }
    );
    const disposePointerLeave = dependencies.runtime.on(documentRef, 'pointerleave', (event) => {
        if (event instanceof PointerEvent && event.pointerType === 'mouse') lastMousePointerPoint = null;
    });

    sync();

    return {
        observeScroll,
        sync,
        reset: () => {
            lastScrollTop = null;
            for (const surface of surfaces) surface.reset();
        },
        dispose: () => {
            disposePointerMove();
            disposePointerLeave();
            for (const surface of surfaces) surface.dispose();
        }
    };
};
