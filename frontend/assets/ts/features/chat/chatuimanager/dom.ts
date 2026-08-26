/* SoAI - Chat UI manager DOM contracts [frontend/assets/ts/features/chat/chatuimanager/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { measureScrollEdges } from '@core/dom/scrollGeometry.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { isFunction } from '@core/typeGuards.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { disposeAutoScrollLockRuntime, setupAutoScrollLockRuntime, syncAutoScrollLockAttribute, syncAutoScrollStateFromScroll } from '@features/chat/chatuimanager/autoScrollLockRuntime.ts';
import { cancelActiveConversationScrollRestore, captureCurrentConversationScrollSnapshot, isConversationScrollRestoreActive } from '@features/chat/chatuimanager/conversationScrollRestoration.ts';
import { clearTimer } from '@features/chat/chatuimanager/state.ts';
import { createMobileAvatarFloatingRuntime } from '@features/chat/chatuimanager/mobileAvatarFloatingRuntime.ts';
import type { ChatUIManagerContext, ElementSelectorKey } from '@features/chat/chatuimanager/types.ts';
import { syncInputWrapperScrollState } from '@features/chat/chatuimanager/scrollState.ts';
import { isMainTimelineAtBottom, isMainTimelineMeasurementAtBottom, measureMainTimelineScroll, type MainTimelineScrollMeasurement } from '@features/chat/mainTimelineScroll.ts';

export function getElement(context: ChatUIManagerContext, key: ElementSelectorKey): HTMLElement | null {
    const cached = context.state.elementCache[key];
    if (cached instanceof HTMLElement && cached.isConnected) {
        return cached;
    }

    const selector = context.elementSelectors[key];
    if (!selector) {
        return null;
    }

    const direct = context.dependencies.optionalUI(selector);
    if (direct instanceof HTMLElement) {
        context.state.elementCache[key] = direct;
        return direct;
    }

    const doc = context.dependencies.dom.getDocument();
    const inBody = context.dependencies.optionalUI(selector, doc.body);
    const resolved = inBody instanceof HTMLElement ? inBody : null;
    context.state.elementCache[key] = resolved;
    return resolved;
}

function updatePreviewsContainerVisibility(context: ChatUIManagerContext): void {
    const container = context.dependencies.optionalUI('.chat-previews-container');
    if (!(container instanceof HTMLElement)) {
        return;
    }

    const preview = getElement(context, 'preview');
    const inputQueuePreview = getElement(context, 'inputQueuePreview');
    const toolApprovalPreview = getElement(context, 'toolApprovalPreview');
    const askUserPreview = getElement(context, 'askUserPreview');
    const secretPromptPreview = getElement(context, 'secretPromptPreview');
    const voiceRecordingPreview = getElement(context, 'voiceRecordingPreview');

    const previewVisible = preview instanceof HTMLElement && !preview.classList.contains(CSS_CLASSES.HIDDEN);
    const pendingVisible = inputQueuePreview instanceof HTMLElement && !inputQueuePreview.classList.contains(CSS_CLASSES.HIDDEN);
    const toolApprovalVisible = toolApprovalPreview instanceof HTMLElement && !toolApprovalPreview.classList.contains(CSS_CLASSES.HIDDEN);
    const askUserVisible = askUserPreview instanceof HTMLElement && !askUserPreview.classList.contains(CSS_CLASSES.HIDDEN);
    const secretPromptVisible = secretPromptPreview instanceof HTMLElement && !secretPromptPreview.classList.contains(CSS_CLASSES.HIDDEN);
    const voiceRecordingVisible = voiceRecordingPreview instanceof HTMLElement && !voiceRecordingPreview.classList.contains(CSS_CLASSES.HIDDEN);
    const eitherVisible = previewVisible || pendingVisible || toolApprovalVisible || askUserVisible || secretPromptVisible || voiceRecordingVisible;

    const messages = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (messages instanceof HTMLElement) {
        const requiresInput = toolApprovalVisible || askUserVisible || secretPromptVisible;
        context.dependencies.updateAttribute(messages, 'data-user-input-required', requiresInput ? 'true' : null);

        const selector = '.chat-message.assistant .message-content.message-content--with-header > .message-actions';
        const actionRows = context.dependencies.queryUI(selector, messages);
        for (let index = 0; index < actionRows.length; index += 1) {
            const actionRow = actionRows[index];
            if (actionRow) {
                context.dependencies.updateAttribute(actionRow, 'data-user-input-required', null);
            }
        }
        if (requiresInput && actionRows.length > 0) {
            const lastActionRow = actionRows[actionRows.length - 1];
            if (lastActionRow) {
                context.dependencies.updateAttribute(lastActionRow, 'data-user-input-required', 'true');
            }
        }
    }

    context.dependencies.toggleClassName(container, CSS_CLASSES.HIDDEN, !eitherVisible);
}

export function setElementVisibility(context: ChatUIManagerContext, key: ElementSelectorKey, shouldShow: boolean): void {
    const element = getElement(context, key);
    if (!element) {
        return;
    }

    context.dependencies.toggleClassName(element, CSS_CLASSES.HIDDEN, !shouldShow);
    context.dependencies.updateAttribute(element, 'aria-hidden', shouldShow ? 'false' : 'true');

    updatePreviewsContainerVisibility(context);
}

export function updateMicrophoneAvailability(context: ChatUIManagerContext): void {
    const hasRecordingSupport = isFunction(navigator?.mediaDevices?.getUserMedia);
    const micCandidates = context.dependencies.queryUI(CHAT_SELECTORS.MICROPHONE_BTN);
    if (micCandidates.length === 0) {
        return;
    }
    for (const candidate of micCandidates) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        context.dependencies.updateProperty(candidate, 'disabled', !hasRecordingSupport);
    }
}

const MESSAGE_WINDOW_EDGE_THRESHOLD_PX = 96;

function disposeScrollListener(context: ChatUIManagerContext): void {
    context.state.scrollDebounceHandler?.cancel?.();
    context.state.scrollDebounceHandler = null;
    context.state.scrollListenerDisposer?.();
    context.state.scrollListenerDisposer = null;
    context.state.scrollListenerMessagesArea = null;
}

export function setupScrollListener(context: ChatUIManagerContext): void {
    const messagesArea = getElement(context, 'messagesArea');
    if (!(messagesArea instanceof HTMLElement)) {
        return;
    }
    const messagesRootCandidate = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES, messagesArea);
    if (!(messagesRootCandidate instanceof HTMLElement)) {
        throw new Error('Chat messages timeline is required for scroll state');
    }
    const messagesRoot = messagesRootCandidate;

    if (context.state.scrollListenerDisposer && context.state.scrollListenerMessagesArea === messagesArea && messagesArea.isConnected) {
        setupAutoScrollLockRuntime(context, messagesArea, messagesRoot, () => scrollToBottom(context));
        return;
    }
    disposeScrollListener(context);
    disposeAutoScrollLockRuntime(context);

    const updateAutoScrollState = (): MainTimelineScrollMeasurement => {
        const measurement = measureMainTimelineScroll(messagesArea);
        syncAutoScrollStateFromScroll(context, messagesArea, isMainTimelineMeasurementAtBottom(measurement), () => scrollToBottom(context));
        return measurement;
    };

    const syncWrapperState = (): void => {
        syncInputWrapperScrollState(context);
    };

    const debouncedHandler = context.dependencies.runtime.createDebouncedHandler(syncWrapperState, 100);
    const avatarFloatingRuntime = createMobileAvatarFloatingRuntime(messagesArea, messagesRoot);
    const handleScroll = (): void => {
        if (isConversationScrollRestoreActive(context)) return;
        const measurement = updateAutoScrollState();
        const edges = measureScrollEdges({ position: measurement.scrollTop, extent: measurement.scrollHeight, viewport: measurement.clientHeight, tolerance: MESSAGE_WINDOW_EDGE_THRESHOLD_PX });
        if (edges.atStart) {
            context.dependencies.drafts.requestMessageWindow('before');
        } else if (edges.atEnd) {
            context.dependencies.drafts.requestMessageWindow('after');
        }
        captureCurrentConversationScrollSnapshot(context);
        avatarFloatingRuntime.schedule();
        debouncedHandler();
    };

    context.state.scrollDebounceHandler = debouncedHandler;
    const scrollDisposer = context.dependencies.runtime.on(messagesArea, 'scroll', handleScroll);
    context.state.scrollListenerDisposer = () => {
        scrollDisposer();
        avatarFloatingRuntime.dispose();
    };
    context.state.scrollListenerMessagesArea = messagesArea;
    updateAutoScrollState();
    setupAutoScrollLockRuntime(context, messagesArea, messagesRoot, () => scrollToBottom(context));
    syncInputWrapperScrollState(context);
    avatarFloatingRuntime.syncImmediately();
}

const requestOlderMessagesIfAtTopNow = (context: ChatUIManagerContext): void => {
    if (isConversationScrollRestoreActive(context)) return;
    const messagesArea = getElement(context, 'messagesArea');
    if (!(messagesArea instanceof HTMLElement)) {
        return;
    }
    const measurement = measureMainTimelineScroll(messagesArea);
    const edges = measureScrollEdges({ position: measurement.scrollTop, extent: measurement.scrollHeight, viewport: measurement.clientHeight, tolerance: MESSAGE_WINDOW_EDGE_THRESHOLD_PX });
    if (edges.atStart) {
        context.dependencies.drafts.requestMessageWindow('before');
    }
};

export function requestOlderMessagesIfAtTop(context: ChatUIManagerContext): void {
    if (isConversationScrollRestoreActive(context)) return;
    if (context.state.olderMessagesRequestTimer !== null) {
        return;
    }
    context.state.olderMessagesRequestTimer = context.dependencies.runtime.setTimer(() => {
        context.state.olderMessagesRequestTimer = null;
        requestOlderMessagesIfAtTopNow(context);
    }, 100);
}

export function scrollToBottom(context: ChatUIManagerContext): void {
    if (isConversationScrollRestoreActive(context)) return;
    const messagesArea = getElement(context, 'messagesArea');
    if (!(messagesArea instanceof HTMLElement)) {
        return;
    }

    context.state.autoScrollUserIntentActive = false;
    const targetScrollTop = Math.max(0, messagesArea.scrollHeight - messagesArea.clientHeight);
    let currentScrollTop = messagesArea.scrollTop;
    if (currentScrollTop !== targetScrollTop) {
        messagesArea.scrollTop = targetScrollTop;
        currentScrollTop = messagesArea.scrollTop;
    }
    if (context.state.autoScrollEnabled) {
        syncAutoScrollLockAttribute(context, messagesArea);
    }
    captureCurrentConversationScrollSnapshot(context);
}

export function forceScrollToBottom(context: ChatUIManagerContext): void {
    if (isConversationScrollRestoreActive(context)) return;
    context.state.autoScrollEnabled = true;
    syncAutoScrollLockAttribute(context, getElement(context, 'messagesArea'));
    scrollToBottom(context);
    syncInputWrapperScrollState(context);
}

export function setAutoScrollEnabled(context: ChatUIManagerContext, enabled: boolean): void {
    if (isConversationScrollRestoreActive(context)) return;
    context.state.autoScrollEnabled = enabled;
    if (enabled) {
        context.state.autoScrollUserIntentActive = false;
    }
    syncAutoScrollLockAttribute(context, getElement(context, 'messagesArea'));
    syncInputWrapperScrollState(context);
}

export function isAutoScrollEnabled(context: ChatUIManagerContext): boolean {
    return context.state.autoScrollEnabled;
}

export function shouldAutoScrollAfterContentUpdate(context: ChatUIManagerContext): boolean {
    const messagesArea = getElement(context, 'messagesArea');
    if (!(messagesArea instanceof HTMLElement)) {
        return true;
    }

    return isMainTimelineAtBottom(messagesArea);
}

export function scheduleScrollToBottom(context: ChatUIManagerContext, delayMs: number = 50): void {
    if (isConversationScrollRestoreActive(context)) return;
    clearTimer(context, context.state.scrollTimer);
    context.state.scrollTimer = context.dependencies.runtime.setTimer(
        () => {
            context.state.scrollTimer = null;
            if (context.state.autoScrollEnabled) {
                scrollToBottom(context);
            }
        },
        Math.max(0, delayMs)
    );
}

export function revealElementFromUserAction(context: ChatUIManagerContext, target: Element | null, options: ScrollIntoViewOptions = {}): void {
    if (!target || !isFunction(target.scrollIntoView)) {
        return;
    }

    cancelActiveConversationScrollRestore(context, true);
    clearTimer(context, context.state.scrollTimer);
    context.state.scrollTimer = null;
    context.state.autoScrollEnabled = false;
    context.state.autoScrollUserIntentActive = true;
    syncAutoScrollLockAttribute(context, getElement(context, 'messagesArea'));
    syncInputWrapperScrollState(context);
    scrollElementIntoView(target, options);
}

export function scrollIntoView(target: Element | null, options: ScrollIntoViewOptions = {}): void {
    if (!target || !isFunction(target.scrollIntoView)) {
        return;
    }

    scrollElementIntoView(target, options);
}

export function clearAttachedFiles(context: ChatUIManagerContext): void {
    const preview = getElement(context, 'preview');
    if (preview) {
        context.dependencies.updateHTML(preview, '');
    }

    setElementVisibility(context, 'preview', false);
}
