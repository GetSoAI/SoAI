/* SoAI - Chat composer auto-hide chrome surface [frontend/assets/ts/features/chat/chatuimanager/chatComposerChromeSurface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { isEditableKeyTarget, isMainTimelineAtBottom } from '@features/chat/mainTimelineScroll.ts';
import { createChatChromeSurfaceController, type ChatChromeSurfaceController } from '@features/chat/chatuimanager/chatChromeSurfaceController.ts';
import { getElement, isAnyElementShown } from '@features/chat/chatuimanager/dom.ts';
import type { ChatUIManagerContext, ElementSelectorKey } from '@features/chat/chatuimanager/types.ts';
import { COMPOSER_STOP_MODE_CLASS } from '@features/chat/chatuimanager/view.ts';

const AUTO_HIDDEN_CLASS = 'chat-input-wrapper--auto-hidden';
const FLOATING_STOP_CLASS = 'chat-input-wrapper--floating-stop';
const INPUT_WRAPPER_SELECTOR = '.chat-input-wrapper';
const CHAT_PAGE_SELECTOR = '.chat-container';
const DRAFT_PREVIEW_KEYS: readonly ElementSelectorKey[] = ['preview', 'inputQueuePreview', 'voiceRecordingPreview'];

const resolveInputWrapper = (context: ChatUIManagerContext): HTMLElement | null => {
    const wrapper = getElement(context, 'input')?.closest(INPUT_WRAPPER_SELECTOR);
    return wrapper instanceof HTMLElement ? wrapper : null;
};

const isPrintableKey = (event: KeyboardEvent): boolean => event.key.length === 1 && event.key !== ' ' && !event.metaKey && (!(event.ctrlKey || event.altKey) || event.getModifierState('AltGraph'));

const isPasteShortcut = (event: KeyboardEvent): boolean => (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'v';

const isTypingRevealKey = (event: KeyboardEvent): boolean => !event.defaultPrevented && !event.isComposing && (isPrintableKey(event) || isPasteShortcut(event));

export const setupChatComposerChromeSurface = (context: ChatUIManagerContext, isGlobalPinned: () => boolean): ChatChromeSurfaceController => {
    const dependencies = context.dependencies;
    const documentRef = dependencies.dom.getDocument();
    let compositionActive = false;
    let stopFloating = false;
    let conversationSelectionActive = false;
    let selectionDragActive = false;

    const isFloatingStop = (target: EventTarget | null): boolean => stopFloating && target instanceof Node && getElement(context, 'actionBtn')?.contains(target) === true;

    const hasDraftActivity = (wrapper: HTMLElement): boolean => {
        const input = getElement(context, 'input');
        const hasText = input instanceof HTMLTextAreaElement && input.value !== '';
        const focused = documentRef.activeElement;
        const composerFocused = wrapper.contains(focused) && !isFloatingStop(focused);
        return hasText || compositionActive || composerFocused || isAnyElementShown(context, DRAFT_PREVIEW_KEYS) || dependencies.session.hasPendingAttachmentProcessing();
    };

    const toggleWrapperClass = (wrapper: HTMLElement, className: string, active: boolean): void => {
        if (wrapper.classList.contains(className) !== active) dependencies.toggleClassName(wrapper, className, active);
    };

    const controller: ChatChromeSurfaceController = createChatChromeSurfaceController(context, {
        isGlobalPinned,
        config: {
            revealEdge: 'bottom',
            resolveElement: () => resolveInputWrapper(context),
            resolveInteractionElements: (wrapper) => [wrapper],
            resolveRevealBounds: (wrapper) => measureLayoutBox(wrapper),
            isPinned: (wrapper) => !dependencies.settings.isAutoHideChatComposerEnabled() || (!dependencies.messageManager.isMessageEditing() && hasDraftActivity(wrapper)),
            isTemporaryHideExempt: (shown) => {
                const messagesArea = getElement(context, 'messagesArea');
                return messagesArea !== null && dependencies.session.getCurrentConversation()?.history?.hasNewer !== true && isMainTimelineAtBottom(messagesArea) && (!selectionDragActive || shown);
            },
            isRevealBlocked: () => dependencies.messageManager.isMessageEditing(),
            isPointerTargetIgnored: isFloatingStop,
            project: (wrapper, visible) => {
                stopFloating = !visible && (stopFloating || getElement(context, 'actionBtn')?.classList.contains(COMPOSER_STOP_MODE_CLASS) === true);
                toggleWrapperClass(wrapper, AUTO_HIDDEN_CLASS, !visible);
                toggleWrapperClass(wrapper, FLOATING_STOP_CLASS, stopFloating);
            }
        }
    });

    const handleCompositionChange = (active: boolean): void => {
        compositionActive = active;
        controller.commit();
    };

    const isTypingRevealTarget = (target: EventTarget | null, input: HTMLTextAreaElement): boolean => {
        if (target === documentRef.body) return true;
        return target instanceof Element && !isEditableKeyTarget(target) && input.closest(CHAT_PAGE_SELECTOR)?.contains(target) === true;
    };

    const handleDocumentKeyDown = (event: Event): void => {
        if (!(event instanceof KeyboardEvent) || !isTypingRevealKey(event) || controller.isShown() || conversationSelectionActive) return;
        const input = getElement(context, 'input');
        if (!(input instanceof HTMLTextAreaElement) || !isTypingRevealTarget(event.target, input) || input.closest('[inert]') !== null || dependencies.messageManager.isMessageEditing()) return;
        controller.reset();
        input.focus({ preventScroll: true });
    };

    const handleSelectionChange = (): void => {
        const selection = documentRef.getSelection();
        const messagesArea = getElement(context, 'messagesArea');
        conversationSelectionActive = false;
        if (selection !== null && !selection.isCollapsed && messagesArea !== null) {
            for (let rangeIndex = 0; rangeIndex < selection.rangeCount; rangeIndex += 1) {
                if (selection.getRangeAt(rangeIndex).intersectsNode(messagesArea)) {
                    conversationSelectionActive = true;
                    break;
                }
            }
        }
        controller.setTemporarilyHidden(conversationSelectionActive);
    };

    const handleSelectionPointer = (event: Event): void => {
        if (!(event instanceof PointerEvent) || event.pointerType !== 'mouse') return;
        if (event.type === 'pointerdown') {
            const messagesArea = getElement(context, 'messagesArea');
            selectionDragActive = event.button === 0 && event.target instanceof Node && messagesArea?.contains(event.target) === true;
        } else if (selectionDragActive && (event.buttons === 0 || event.type === 'pointercancel')) {
            selectionDragActive = false;
            controller.commit();
        }
    };

    const wrapper = resolveInputWrapper(context);
    const input = getElement(context, 'input');
    if (wrapper !== null && input !== null) {
        for (const eventType of ['pointerdown', 'pointerup', 'pointercancel', 'pointermove']) {
            controller.addDisposer(dependencies.runtime.on(documentRef, eventType, handleSelectionPointer, { passive: true }));
        }
        controller.addDisposer(dependencies.runtime.on(documentRef, 'selectionchange', handleSelectionChange));
        controller.addDisposer(dependencies.runtime.on(documentRef, 'keydown', handleDocumentKeyDown));
        controller.addDisposer(dependencies.runtime.on(wrapper, 'focusin', () => controller.commit(), { passive: true }));
        controller.addDisposer(dependencies.runtime.on(input, 'compositionstart', () => handleCompositionChange(true), { passive: true }));
        controller.addDisposer(dependencies.runtime.on(input, 'compositionend', () => handleCompositionChange(false), { passive: true }));
        handleSelectionChange();
    }

    return controller;
};
