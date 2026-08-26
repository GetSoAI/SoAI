/* SoAI - Chat UI manager state [frontend/assets/ts/features/chat/chatuimanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { disposeAutoScrollLockRuntime } from '@features/chat/chatuimanager/autoScrollLockRuntime.ts';
import { disposeConversationScrollRestoration } from '@features/chat/chatuimanager/conversationScrollRestoration.ts';
import type { ChatUIManagerContext, ChatUiManagerDependencies, ChatUIManagerState, ElementSelectorKey } from '@features/chat/chatuimanager/types.ts';

function createElementSelectors(): Record<ElementSelectorKey, string> {
    return {
        input: CHAT_SELECTORS.INPUT,
        actionBtn: CHAT_SELECTORS.ACTION_BTN,
        attachBtn: CHAT_SELECTORS.ATTACH_BTN,
        messagesArea: CHAT_SELECTORS.MESSAGES_AREA,
        preview: CHAT_SELECTORS.PREVIEW,
        inputQueuePreview: CHAT_SELECTORS.INPUT_QUEUE_PREVIEW,
        toolApprovalPreview: CHAT_SELECTORS.TOOL_APPROVAL_PREVIEW,
        askUserPreview: CHAT_SELECTORS.ASK_USER_PREVIEW,
        secretPromptPreview: CHAT_SELECTORS.SECRET_PROMPT_PREVIEW,
        voiceRecordingPreview: CHAT_SELECTORS.VOICE_RECORDING_PREVIEW
    };
}

function createChatUIManagerState(): ChatUIManagerState {
    return {
        autoScrollEnabled: true,
        autoScrollUserIntentActive: false,
        autoScrollIntentDisposers: [],
        elementCache: {},
        scrollTimer: null,
        olderMessagesRequestTimer: null,
        scrollDebounceHandler: null,
        scrollListenerDisposer: null,
        scrollListenerMessagesArea: null,
        messagesAutoScrollLockDisposer: null,
        messagesAutoScrollLockArea: null,
        conversationScrollSnapshotByConversationId: new Map(),
        pendingConversationScrollRestoreConversationId: null,
        activeConversationScrollRestore: null,
        conversationScrollRestoreGeneration: 0,
        attachedFilesPreviewLayoutDisposer: null,
        advancedScrollPreviewDisposer: null,
        advancedScrollPreviewOverlay: null,
        advancedScrollPreviewVisibilityController: null,
        activeConversationTransitionId: null,
        messagesAreaInsetsDisposer: null,
        modalPresenter: null,
        inlineActivityScrollStateByKey: new Map()
    };
}

export function createChatUIManagerContext(dependencies: ChatUiManagerDependencies): ChatUIManagerContext {
    return {
        dependencies,
        elementSelectors: createElementSelectors(),
        state: createChatUIManagerState()
    };
}

export function clearTimer(context: ChatUIManagerContext, timer: number | null | undefined): void {
    if (timer !== null && timer !== undefined) {
        context.dependencies.runtime.clearTimer(timer);
    }
}

export function disposeScrollRuntime(context: ChatUIManagerContext): void {
    clearTimer(context, context.state.scrollTimer);
    context.state.scrollTimer = null;
    clearTimer(context, context.state.olderMessagesRequestTimer);
    context.state.olderMessagesRequestTimer = null;

    context.state.scrollDebounceHandler?.cancel?.();
    context.state.scrollDebounceHandler = null;

    context.state.scrollListenerDisposer?.();
    context.state.scrollListenerDisposer = null;
    context.state.scrollListenerMessagesArea = null;

    disposeAutoScrollLockRuntime(context);

    disposeConversationScrollRestoration(context);
}
