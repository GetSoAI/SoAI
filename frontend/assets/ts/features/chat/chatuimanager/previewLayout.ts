/* SoAI - Chat preview container layout ownership [frontend/assets/ts/features/chat/chatuimanager/previewLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { getElement } from '@features/chat/chatuimanager/dom.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';

const CHAT_PREVIEWS_CONTAINER_BOTTOM_VAR = '--chat-previews-container-bottom';
const CHAT_PREVIEWS_CONTAINER_LEFT_VAR = '--chat-previews-container-left';
const CHAT_PREVIEWS_CONTAINER_RIGHT_VAR = '--chat-previews-container-right';
const CHAT_MAIN_CONTAINER_SELECTOR = '.chat-main-container';
const CHAT_INPUT_ACTIONS_SELECTOR = '.chat-input-actions';
const AGENT_MODE_POPUP_SELECTOR = '.agent-mode-popup';

function applyPreviewsContainerInsets(context: ChatUIManagerContext, containerElement: HTMLElement, mainContainer: HTMLElement, inputWrapper: HTMLElement, chatInput: HTMLTextAreaElement, popupWidth: number, extraLeftPadding: number): void {
    const mainContainerRect = measureLayoutBox(mainContainer);
    const wrapperRect = measureLayoutBox(inputWrapper);
    const inputRect = measureLayoutBox(chatInput);

    const rawBottomInset = mainContainerRect.bottom - wrapperRect.top;
    const rawLeftInset = inputRect.left - mainContainerRect.left;
    const rawRightInset = mainContainerRect.right - inputRect.right;

    const bottomInset = Math.max(0, rawBottomInset);
    const clampedPopupWidth = clampNumber(popupWidth, 0, inputRect.width);
    const clampedExtraPadding = clampNumber(extraLeftPadding, 0, inputRect.width);
    const leftInset = Math.max(0, rawLeftInset + clampedPopupWidth + clampedExtraPadding);
    const rightInset = Math.max(0, rawRightInset);

    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_BOTTOM_VAR, `calc(${bottomInset}px + var(--chat-previews-container-gap))`);
    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_LEFT_VAR, `${leftInset}px`);
    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_RIGHT_VAR, `${rightInset}px`);
}

function clearPreviewsContainerInsets(context: ChatUIManagerContext, containerElement: HTMLElement): void {
    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_BOTTOM_VAR, null);
    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_LEFT_VAR, null);
    context.dependencies.dom.setStyle(containerElement, CHAT_PREVIEWS_CONTAINER_RIGHT_VAR, null);
}

export function setupPreviewsContainerLayout(context: ChatUIManagerContext): void {
    if (context.state.attachedFilesPreviewLayoutDisposer) {
        return;
    }

    const previewsContainer = context.dependencies.optionalUI('.chat-previews-container');
    if (!(previewsContainer instanceof HTMLElement)) {
        return;
    }

    const inputElement = getElement(context, 'input');
    if (!(inputElement instanceof HTMLTextAreaElement)) {
        return;
    }

    const mainContainer = previewsContainer.closest(CHAT_MAIN_CONTAINER_SELECTOR);
    if (!(mainContainer instanceof HTMLElement)) {
        return;
    }

    const wrapper = inputElement.parentElement;
    if (!(wrapper instanceof HTMLElement)) {
        return;
    }

    const actionsElement = context.dependencies.optionalUI(CHAT_INPUT_ACTIONS_SELECTOR, wrapper);
    const actions = actionsElement instanceof HTMLElement ? actionsElement : null;
    const messagesAreaElement = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    const messagesRootElement = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES);
    if (!(messagesAreaElement instanceof HTMLElement) || !(messagesRootElement instanceof HTMLElement)) {
        return;
    }
    const win = context.dependencies.dom.getDocument().defaultView;
    if (!win || typeof win.ResizeObserver !== 'function' || typeof win.MutationObserver !== 'function') {
        return;
    }
    const coordinator = acquireMainTimelineCoordinator(messagesAreaElement, messagesRootElement);

    let popupResizeDisposer: (() => void) | null = null;
    let observedPopup: HTMLElement | null = null;

    const resolvePopupWidth = (): number => {
        const popupElement = context.dependencies.optionalUI(AGENT_MODE_POPUP_SELECTOR, wrapper);
        if (!(popupElement instanceof HTMLElement)) {
            return 0;
        }
        return measureLayoutBox(popupElement).width;
    };

    const update = (): void => {
        if (!previewsContainer.isConnected || !inputElement.isConnected || !mainContainer.isConnected) {
            clearPreviewsContainerInsets(context, previewsContainer);
            return;
        }
        if (previewsContainer.classList.contains('u-hidden')) {
            clearPreviewsContainerInsets(context, previewsContainer);
            return;
        }

        const actionsRect = actions ? measureLayoutBox(actions) : null;
        const inputRect = measureLayoutBox(inputElement);
        const actionsOverlapInput = actionsRect !== null && actionsRect.left < inputRect.right && actionsRect.right > inputRect.left && actionsRect.top < inputRect.bottom && actionsRect.bottom > inputRect.top;
        if (actionsOverlapInput) {
            clearPreviewsContainerInsets(context, previewsContainer);
            return;
        }

        const previewsRect = measureLayoutBox(previewsContainer);
        const verticalGap = inputRect.top - previewsRect.bottom;
        const extraLeftPadding = verticalGap > 0 ? verticalGap : 0;

        applyPreviewsContainerInsets(context, previewsContainer, mainContainer, wrapper, inputElement, resolvePopupWidth(), extraLeftPadding);
    };

    const scheduleUpdate = (): void => {
        coordinator.scheduleFrame('previews-container-layout', () => () => update());
    };

    const attachPopupObserver = (): void => {
        const popupElement = context.dependencies.optionalUI(AGENT_MODE_POPUP_SELECTOR, wrapper);
        if (!(popupElement instanceof HTMLElement)) {
            if (popupResizeDisposer) {
                popupResizeDisposer();
                popupResizeDisposer = null;
                observedPopup = null;
            }
            return;
        }

        if (observedPopup === popupElement) {
            return;
        }

        popupResizeDisposer?.();
        popupResizeDisposer = coordinator.observeResize(popupElement);
        observedPopup = popupElement;
    };

    const resizeTargets = new Set<Element>([mainContainer, previewsContainer, wrapper, inputElement]);
    if (actions) {
        resizeTargets.add(actions);
    }
    const resizeObservationDisposers = Array.from(resizeTargets, (target) => coordinator.observeResize(target));
    const resizeSubscriptionDisposer = coordinator.subscribeResize((entries) => {
        if (entries.some((entry) => resizeTargets.has(entry.target) || entry.target === observedPopup)) {
            scheduleUpdate();
        }
    });

    const mutationObserver = new win.MutationObserver(() => {
        attachPopupObserver();
        scheduleUpdate();
    });
    mutationObserver.observe(wrapper, { childList: true });
    mutationObserver.observe(previewsContainer, { attributes: true, attributeFilter: ['class'] });

    attachPopupObserver();
    update();

    const windowDisposer = context.dependencies.runtime.on(win, 'resize', () => scheduleUpdate());
    const scaleDisposer = context.dependencies.runtime.on(win, INTERFACE_SCALE_CHANGED_EVENT, () => scheduleUpdate());

    context.state.attachedFilesPreviewLayoutDisposer = () => {
        windowDisposer();
        scaleDisposer();
        mutationObserver.disconnect();
        resizeSubscriptionDisposer();
        for (const disposeResizeObservation of resizeObservationDisposers) {
            disposeResizeObservation();
        }
        popupResizeDisposer?.();
        popupResizeDisposer = null;
        observedPopup = null;
        coordinator.cancelFrame('previews-container-layout');
        coordinator.release();
        clearPreviewsContainerInsets(context, previewsContainer);
    };
}
