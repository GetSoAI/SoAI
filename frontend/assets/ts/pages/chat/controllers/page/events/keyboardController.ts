/* SoAI - Chat page keyboard controller [frontend/assets/ts/pages/chat/controllers/page/events/keyboardController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { isElementNode } from '@core/typeGuards.ts';
import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { CHAT_ACTIONS, CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX, isMarkdownTableHeaderLinkTarget, optionalAskUserCancelButton, resolveMarkdownTableSortHeader } from '@features/chat/public.ts';
import { handleAskUserHotkeyAction, handleAskUserSubmitHotkey } from '@pages/chat/controllers/page/events/askUserSubmitHotkey.ts';
import { resolveChatInputTarget } from '@pages/chat/controllers/page/events/chatInputTargetController.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { isActionElementDisabled } from '@pages/chat/controllers/page/events/dispatch.ts';
import { handleConversationRenameKeydown } from '@pages/chat/controllers/page/events/events.ts';
import { resolveNormalizedMessageIdForTarget } from '@pages/chat/controllers/page/events/messageTargetResolutionController.ts';

const resolveSendButton = (host: ChatRootEventsHost): HTMLButtonElement | null => {
    const button = host.composer.resolveSendMessageButton();
    if (!(button instanceof HTMLButtonElement)) {
        return null;
    }
    return button;
};

const handleAskUserCancelHotkey = (host: ChatRootEventsHost, target: Element, event: KeyboardEvent): boolean => {
    if (event.key !== 'Escape') {
        return false;
    }
    return handleAskUserHotkeyAction(host, target, event, {
        operationId: 'chat:askUserCancelHotkey',
        action: 'chat:ask-user-cancel',
        resolveButton: (preview) => optionalAskUserCancelButton(preview)
    });
};

const dispatchComposerPrimaryHotkey = (host: ChatRootEventsHost, event: KeyboardEvent, operationId: string, action: typeof CHAT_ACTIONS.SEND_OR_STOP | typeof CHAT_ACTIONS.STOP_STREAMING = CHAT_ACTIONS.SEND_OR_STOP): boolean => {
    const sendButton = resolveSendButton(host);
    if (!(sendButton instanceof HTMLButtonElement)) {
        return false;
    }
    const admission = host.composer.resolveCurrentTurnAdmission();
    if (isActionElementDisabled(sendButton) && (admission === null || admission.phase === 'inactive')) {
        return true;
    }
    if (action === CHAT_ACTIONS.STOP_STREAMING) {
        host.shell.dispatchDataAction(action, sendButton, event);
    } else {
        host.shell.runUiTask(operationId, () => host.shell.dispatchDataAction(action, sendButton, event));
    }
    return true;
};

const createSendButtonLoadingClear = (button: HTMLButtonElement | null): (() => void) | null => {
    return button === null ? null : beginLoadingButtonWithClear(button);
};

const sendMessageClearingOnCommit = async (host: ChatRootEventsHost, clearLoading: (() => void) | null): Promise<void> => {
    await host.composer.sendMessage(clearLoading === null ? {} : { onEffectiveSendCommitted: clearLoading });
};

const submitChatInputTabAction = async (host: ChatRootEventsHost, clearLoading: (() => void) | null): Promise<void> => {
    const admission = await host.composer.resolveSyncedCurrentTurnAdmission();
    if (admission?.canQueuePrompt === true || admission?.canSteerPrompt === true) {
        const outcome = await host.composer.queueConversationInputFromComposer('queued');
        if (outcome !== 'not-admitted') {
            return;
        }
        await sendMessageClearingOnCommit(host, clearLoading);
        return;
    }
    await sendMessageClearingOnCommit(host, clearLoading);
};

const handleChatInputHistoryHotkey = (host: ChatRootEventsHost, event: KeyboardEvent, input: HTMLTextAreaElement, direction: 'up' | 'down'): void => {
    const handled = host.composer.handleChatInputHistoryNavigation(input, direction);
    if (handled) {
        event.preventDefault();
    }
};

const handleRootKeydown = (host: ChatRootEventsHost, event: Event): void => {
    if (!(event instanceof KeyboardEvent)) {
        return;
    }
    if (event.key === 'Escape' && host.conversations.isConversationSelectionActive()) {
        event.preventDefault();
        host.conversations.exitConversationSelectMode();
        return;
    }
    if (host.shell.handleAgentKeyDown(event)) {
        return;
    }
    const target = event.target;
    if (!isElementNode(target)) {
        return;
    }
    if (handleAskUserCancelHotkey(host, target, event)) {
        return;
    }
    if (handleAskUserSubmitHotkey(host, target, event)) {
        return;
    }
    if (event.key === 'Escape' && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.isComposing && !event.repeat) {
        const admission = host.composer.resolveCurrentTurnAdmission();
        if (admission?.canStop === true) {
            event.preventDefault();
            dispatchComposerPrimaryHotkey(host, event, 'chat:stopStreamingHotkey', CHAT_ACTIONS.STOP_STREAMING);
            return;
        }
    }
    const chatInput = resolveChatInputTarget(target);
    if (chatInput && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.isComposing) {
            return;
        }
        const selectionStart = chatInput.selectionStart;
        const selectionEnd = chatInput.selectionEnd;
        if (selectionStart === null || selectionEnd === null || selectionStart !== selectionEnd) {
            return;
        }

        if (event.key === 'ArrowUp') {
            if (selectionStart !== 0) {
                return;
            }
            handleChatInputHistoryHotkey(host, event, chatInput, 'up');
            return;
        }

        if (selectionEnd !== chatInput.value.length) {
            return;
        }
        handleChatInputHistoryHotkey(host, event, chatInput, 'down');
        return;
    }
    if (handleConversationRenameKeydown(host, target, event)) {
        return;
    }
    const markdownTableHeader = resolveMarkdownTableSortHeader(target);
    if (markdownTableHeader !== null && (event.key === 'Enter' || event.key === ' ')) {
        if (isMarkdownTableHeaderLinkTarget(target, markdownTableHeader)) {
            return;
        }
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.isComposing || event.repeat) {
            return;
        }
        event.preventDefault();
        host.shell.dispatchDataAction(CHAT_ACTIONS.SORT_MARKDOWN_TABLE, markdownTableHeader, event);
        return;
    }
    if (target.matches('.conversation-title') && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        if (measureLayoutViewport(host.shell.ensureRootElement()).width <= CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX) {
            return;
        }
        if (!(target instanceof HTMLElement)) {
            return;
        }
        host.shell.dispatchDataAction('chat:start-conversation-title-edit', target, event);
        return;
    }
    if (chatInput && event.key === 'Tab') {
        if (event.altKey || event.ctrlKey || event.metaKey || event.isComposing) {
            return;
        }
        const queuedText = readTrimmedInputValue(chatInput);
        const attachmentCount = host.composer.getComposerAttachmentCount();
        if (!queuedText && attachmentCount === 0) {
            return;
        }
        event.preventDefault();
        const sendButton = resolveSendButton(host);
        if (sendButton !== null && isActionElementDisabled(sendButton)) {
            return;
        }
        const clearLoading = createSendButtonLoadingClear(sendButton);
        host.shell.runUiTask('chat:submitChatInputTab', async () => {
            try {
                await submitChatInputTabAction(host, clearLoading);
            } finally {
                clearLoading?.();
            }
        });
        return;
    }
    if (chatInput && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        dispatchComposerPrimaryHotkey(host, event, 'chat:sendOrStopHotkey');
        return;
    }
    if (chatInput && event.key === 'Enter' && !event.shiftKey && !event.altKey && !event.isComposing && !event.repeat && !host.composer.isCtrlEnterSendRequired()) {
        event.preventDefault();
        dispatchComposerPrimaryHotkey(host, event, 'chat:sendOrStopHotkey');
        return;
    }
    if (target.matches('.message-edit-input') && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        if (host.composer.isCurrentConversationStreaming()) {
            return;
        }
        const normalizedMessageId = resolveNormalizedMessageIdForTarget(host, target);
        if (!normalizedMessageId) {
            return;
        }
        host.messages.saveEditedMessage(normalizedMessageId);
    }
};

export { handleRootKeydown };
