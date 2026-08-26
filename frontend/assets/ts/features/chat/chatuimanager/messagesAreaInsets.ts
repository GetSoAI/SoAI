/* SoAI - Chat message area floating-input inset ownership [frontend/assets/ts/features/chat/chatuimanager/messagesAreaInsets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { dom } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';

const CSS_VAR_MESSAGES_PADDING_BOTTOM = '--chat-messages-padding-bottom';
const CSS_VAR_CONVERSATION_HEADER_HEIGHT = '--chat-conversation-header-height';
const CSS_VAR_PLAN_OVERLAY_HEIGHT = '--chat-plan-overlay-height';
const CSS_VAR_PLAN_HEADER_HEIGHT = '--chat-plan-header-height';
const CSS_VAR_PLAN_DIVIDER_HEIGHT = '--chat-plan-divider-height';
const CSS_VAR_NATIVE_SCROLLBAR_GUTTER = '--chat-native-scrollbar-gutter-width';
const INPUT_WRAPPER_SELECTOR = '.chat-input-wrapper';
const CONVERSATION_HEADER_SELECTOR = '.chat-conversation-header';
const PLAN_OVERLAY_SELECTOR = '.agent-todo-panel-container';
const PLAN_HEADER_SELECTOR = '.agent-todo-panel-header';
const PLAN_PANEL_SELECTOR = '.agent-todo-panel';
const PLAN_BODY_SELECTOR = '.agent-todo-panel-body';
const PLAN_COLLAPSED_CLASS = 'agent-todo-panel--collapsed';
const PLAN_VISIBILITY_ATTRIBUTE = 'data-agent-todo-panel-visibility';
const PREVIEWS_CONTAINER_SELECTOR = '.chat-previews-container';
const OVERLAY_SCROLLBAR_GUTTER_FALLBACK_PX = 8;

export const setupMessagesAreaInsets = (context: ChatUIManagerContext): (() => void) | null => {
    const messagesAreaCandidate = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesAreaCandidate instanceof HTMLElement)) {
        return null;
    }
    const messagesArea = messagesAreaCandidate;
    const messagesRootCandidate = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES);
    if (!(messagesRootCandidate instanceof HTMLElement)) {
        return null;
    }
    const messagesRoot = messagesRootCandidate;

    const inputWrapperCandidate = context.dependencies.optionalUI(INPUT_WRAPPER_SELECTOR);
    if (!(inputWrapperCandidate instanceof HTMLElement)) {
        return null;
    }
    const inputWrapper = inputWrapperCandidate;

    const conversationHeaderCandidate = context.dependencies.optionalUI(CONVERSATION_HEADER_SELECTOR);
    const conversationHeader = conversationHeaderCandidate instanceof HTMLElement ? conversationHeaderCandidate : null;
    const headerStyleTarget = conversationHeader?.parentElement instanceof HTMLElement ? conversationHeader.parentElement : messagesArea;

    const planOverlayCandidate = context.dependencies.optionalUI(PLAN_OVERLAY_SELECTOR);
    const planOverlay = planOverlayCandidate instanceof HTMLElement ? planOverlayCandidate : null;

    const previewsContainerCandidate = context.dependencies.optionalUI(PREVIEWS_CONTAINER_SELECTOR);
    const previewsContainer = previewsContainerCandidate instanceof HTMLElement ? previewsContainerCandidate : null;

    const win = context.dependencies.dom.getDocument().defaultView;
    if (!win) {
        return null;
    }
    if (typeof win.ResizeObserver !== 'function' || typeof win.MutationObserver !== 'function') {
        return null;
    }
    const coordinator = acquireMainTimelineCoordinator(messagesArea, messagesRoot);

    const baselinePaddingBottomPx = (() => {
        const computed = win.getComputedStyle(messagesArea);
        const parsed = Number.parseFloat(computed.paddingBottom);
        return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
    })();
    const messageGapPx = (() => {
        if (!messagesRoot.isConnected) {
            return 0;
        }
        const computed = win.getComputedStyle(messagesRoot);
        const parsed = Number.parseFloat(computed.rowGap || computed.gap);
        return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
    })();

    const clearInsetStyles = (): void => {
        context.dependencies.dom.setStyle(messagesArea, CSS_VAR_MESSAGES_PADDING_BOTTOM, null);
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_CONVERSATION_HEADER_HEIGHT, null);
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_OVERLAY_HEIGHT, null);
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_HEADER_HEIGHT, null);
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_DIVIDER_HEIGHT, null);
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_NATIVE_SCROLLBAR_GUTTER, null);
    };

    const apply = (): void => {
        if (!messagesArea.isConnected || !inputWrapper.isConnected) {
            clearInsetStyles();
            return;
        }
        const measuredScrollbarGutterPx = Math.max(0, Math.round(messagesArea.offsetWidth - messagesArea.clientWidth));
        const nativeScrollbarGutterPx = measuredScrollbarGutterPx > 0 ? measuredScrollbarGutterPx : OVERLAY_SCROLLBAR_GUTTER_FALLBACK_PX;
        context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_NATIVE_SCROLLBAR_GUTTER, `${nativeScrollbarGutterPx}px`);
        if (conversationHeader && conversationHeader.isConnected) {
            const headerRect = measureLayoutBox(conversationHeader);
            if (headerRect.height > 0) {
                context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_CONVERSATION_HEADER_HEIGHT, `${Math.round(headerRect.height)}px`);
            }
        }
        if (planOverlay && planOverlay.isConnected) {
            const planRect = measureLayoutBox(planOverlay);
            const panelHeightPx = Math.max(0, planRect.height);
            context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_OVERLAY_HEIGHT, `${Math.round(panelHeightPx)}px`);
            const planHeaderCandidate = dom.resolve(PLAN_HEADER_SELECTOR, planOverlay);
            const planHeaderHeightPx = planHeaderCandidate instanceof HTMLElement ? measureLayoutBox(planHeaderCandidate).height : 0;
            if (planHeaderHeightPx > 0) {
                context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_HEADER_HEIGHT, `${Math.round(planHeaderHeightPx)}px`);
            }
            const planPanel = dom.resolve(PLAN_PANEL_SELECTOR, planOverlay);
            const isCollapsed = planPanel instanceof HTMLElement && planPanel.classList.contains(PLAN_COLLAPSED_CLASS);
            const hasBody = dom.resolve(PLAN_BODY_SELECTOR, planOverlay) instanceof HTMLElement;
            if (panelHeightPx > 0 && hasBody && !isCollapsed && planHeaderHeightPx > 0) {
                context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_DIVIDER_HEIGHT, 'var(--border-width-1)');
            } else {
                context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_DIVIDER_HEIGHT, '0px');
            }
        } else {
            context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_OVERLAY_HEIGHT, '0px');
            context.dependencies.dom.setStyle(headerStyleTarget, CSS_VAR_PLAN_DIVIDER_HEIGHT, '0px');
        }
        const areaRect = measureLayoutBox(messagesArea);
        const overlayTops: number[] = [];
        const inputRect = measureLayoutBox(inputWrapper);
        overlayTops.push(inputRect.top);
        if (previewsContainer && previewsContainer.isConnected && !previewsContainer.classList.contains('u-hidden')) {
            const previewsRect = measureLayoutBox(previewsContainer);
            if (previewsRect.height > 0) {
                overlayTops.push(previewsRect.top);
            }
        }
        const overlapPx = areaRect.bottom - Math.min(...overlayTops);
        const clampedOverlapPx = clampNumber(overlapPx, 0, areaRect.height);
        const padded = Math.max(baselinePaddingBottomPx, clampedOverlapPx + messageGapPx);
        context.dependencies.dom.setStyle(messagesArea, CSS_VAR_MESSAGES_PADDING_BOTTOM, `${Math.round(padded)}px`);
    };

    const scheduleApply = (): void => {
        coordinator.scheduleFrame('messages-area-insets', () => () => apply());
    };

    const resizeTargets = new Set<Element>([messagesArea, inputWrapper]);
    if (conversationHeader) {
        resizeTargets.add(conversationHeader);
    }
    if (planOverlay) {
        resizeTargets.add(planOverlay);
    }
    if (previewsContainer) {
        resizeTargets.add(previewsContainer);
    }
    const resizeObservationDisposers = Array.from(resizeTargets, (target) => coordinator.observeResize(target));
    const resizeSubscriptionDisposer = coordinator.subscribeResize((entries) => {
        if (entries.some((entry) => resizeTargets.has(entry.target))) {
            scheduleApply();
        }
    });

    const mutationObserver = new win.MutationObserver(scheduleApply);
    if (planOverlay) {
        mutationObserver.observe(planOverlay, { attributes: true, attributeFilter: ['class', 'style', PLAN_VISIBILITY_ATTRIBUTE], childList: true, subtree: true });
    }

    const windowDisposer = context.dependencies.runtime.on(win, 'resize', () => scheduleApply());
    const scaleDisposer = context.dependencies.runtime.on(win, INTERFACE_SCALE_CHANGED_EVENT, () => scheduleApply());

    apply();

    return () => {
        windowDisposer();
        scaleDisposer();
        mutationObserver.disconnect();
        resizeSubscriptionDisposer();
        for (const disposeResizeObservation of resizeObservationDisposers) {
            disposeResizeObservation();
        }
        coordinator.cancelFrame('messages-area-insets');
        coordinator.release();
        clearInsetStyles();
    };
};
