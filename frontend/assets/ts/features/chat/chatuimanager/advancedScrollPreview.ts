/* SoAI - Chat advanced scroll preview installation [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { createAdvancedScrollPreviewRuntime } from '@features/chat/chatuimanager/advancedScrollPreviewRuntime.ts';
import type { AdvancedScrollPreviewElements, ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const ADVANCED_SCROLL_SELECTOR = '.chat-advanced-scroll';
const ADVANCED_SCROLL_CANVAS_SELECTOR = '.chat-advanced-scroll-canvas';
const ADVANCED_SCROLL_VIEWPORT_SELECTOR = '.chat-advanced-scroll-viewport';
const ADVANCED_SCROLL_FADE_TOP_SELECTOR = '.chat-advanced-scroll-fade--top';
const ADVANCED_SCROLL_FADE_BOTTOM_SELECTOR = '.chat-advanced-scroll-fade--bottom';

export function setupAdvancedScrollPreview(context: ChatUIManagerContext): void {
    const messagesAreaCandidate = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesAreaCandidate instanceof HTMLElement)) {
        return;
    }
    const messagesArea = messagesAreaCandidate;

    const messagesRootCandidate = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES, messagesArea);
    if (!(messagesRootCandidate instanceof HTMLElement)) {
        return;
    }
    const messagesRoot = messagesRootCandidate;

    const overlayCandidate = context.dependencies.optionalUI(ADVANCED_SCROLL_SELECTOR, messagesArea.parentElement ?? undefined);
    if (!(overlayCandidate instanceof HTMLElement)) {
        return;
    }
    const overlay = overlayCandidate;

    if (context.state.advancedScrollPreviewDisposer) {
        const previousOverlay = context.state.advancedScrollPreviewOverlay;
        if (previousOverlay === overlay && overlay.isConnected) {
            return;
        }
        context.state.advancedScrollPreviewDisposer();
        context.state.advancedScrollPreviewDisposer = null;
        context.state.advancedScrollPreviewOverlay = null;
    }

    const canvasCandidate = context.dependencies.optionalUI(ADVANCED_SCROLL_CANVAS_SELECTOR, overlay);
    if (!(canvasCandidate instanceof HTMLElement)) {
        return;
    }
    const canvas = canvasCandidate;

    const viewportCandidate = context.dependencies.optionalUI(ADVANCED_SCROLL_VIEWPORT_SELECTOR, overlay);
    const fadeTopCandidate = context.dependencies.optionalUI(ADVANCED_SCROLL_FADE_TOP_SELECTOR, overlay);
    const fadeBottomCandidate = context.dependencies.optionalUI(ADVANCED_SCROLL_FADE_BOTTOM_SELECTOR, overlay);
    if (!(viewportCandidate instanceof HTMLElement) || !(fadeTopCandidate instanceof HTMLElement) || !(fadeBottomCandidate instanceof HTMLElement)) {
        return;
    }
    const viewport = viewportCandidate;
    const fadeTop = fadeTopCandidate;
    const fadeBottom = fadeBottomCandidate;

    const resolved: AdvancedScrollPreviewElements = {
        messagesArea,
        messagesRoot,
        overlay,
        canvas,
        viewport,
        fadeTop,
        fadeBottom
    };

    const disposer = createAdvancedScrollPreviewRuntime(context, resolved);
    if (!disposer) {
        return;
    }
    context.state.advancedScrollPreviewDisposer = disposer;
    context.state.advancedScrollPreviewOverlay = overlay;
}
