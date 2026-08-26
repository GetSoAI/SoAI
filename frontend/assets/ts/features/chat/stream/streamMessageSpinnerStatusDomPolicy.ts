/* SoAI - Direct DOM resolution for the streaming spinner/status area in chat messages [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHTMLElement } from '@core/typeGuards.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
const STATUS_TEXT_ATTRIBUTE_NAME = 'data-stream-spinner-text';
const STATUS_TEXT_BODY_ATTRIBUTE_NAME = 'data-stream-spinner-text-body';
const STATUS_ATTRIBUTE_NAME = 'data-stream-spinner-status';
const SPINNER_CLASS_NAME = 'message-streaming-spinner-indicator';
const ACTION_BUTTONS_CLASS_NAME = 'message-action-buttons';
const ACTION_BUTTONS_LEFT_CLASS_NAME = 'message-action-buttons-left';

const resolveDirectChild = (root: HTMLElement, predicate: (element: HTMLElement) => boolean): HTMLElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && predicate(child)) {
            return child;
        }
    }
    return null;
};

const isStatusElement = (element: HTMLElement): boolean => {
    return element.getAttribute(STATUS_ATTRIBUTE_NAME) === 'true';
};

const isStatusTextElement = (element: HTMLElement): boolean => {
    return element.getAttribute(STATUS_TEXT_ATTRIBUTE_NAME) === 'true';
};

const isStatusTextBodyElement = (element: HTMLElement): boolean => {
    return element.getAttribute(STATUS_TEXT_BODY_ATTRIBUTE_NAME) === 'true';
};

const isSpinnerElement = (element: HTMLElement): boolean => {
    return element.classList.contains(SPINNER_CLASS_NAME);
};

const isSettledActionButtonsElement = (element: HTMLElement): boolean => {
    return element.classList.contains(ACTION_BUTTONS_CLASS_NAME);
};

const isActionButtonsLeftElement = (element: HTMLElement): boolean => {
    return element.classList.contains(ACTION_BUTTONS_LEFT_CLASS_NAME);
};

const isActiveMessageActionButton = (element: HTMLElement): boolean => {
    if (!(element instanceof HTMLButtonElement)) {
        return false;
    }
    if (!element.classList.contains('message-action')) {
        return false;
    }
    if (element.disabled || element.hidden || element.getAttribute('aria-disabled') === 'true') {
        return false;
    }
    return !element.classList.contains('u-hidden');
};

const hasActiveActionButtonDescendant = (root: HTMLElement): boolean => {
    const stack: Element[] = [root];
    while (stack.length > 0) {
        const current = stack.pop();
        if (!(current instanceof HTMLElement)) {
            continue;
        }
        if (isActiveMessageActionButton(current)) {
            return true;
        }
        const children = current.children;
        for (let index = children.length - 1; index >= 0; index -= 1) {
            const child = children[index];
            if (child instanceof Element) {
                stack.push(child);
            }
        }
    }
    return false;
};

const resolveMessageActionsElement = (messageRoot: HTMLElement): HTMLElement | null => {
    return resolveAssistantMessageParts(messageRoot)?.actions ?? null;
};

const readBooleanAttribute = (element: HTMLElement | null, attributeName: string): boolean => {
    return element?.getAttribute(attributeName) === 'true';
};

const resolveActionFlowChild = (actionsElement: HTMLElement, predicate: (element: HTMLElement) => boolean): HTMLElement | null => {
    const actionButtons = resolveDirectChild(actionsElement, isSettledActionButtonsElement);
    if (!isHTMLElement(actionButtons)) {
        return null;
    }
    const left = resolveDirectChild(actionButtons, isActionButtonsLeftElement);
    if (!isHTMLElement(left)) {
        throw new Error('Streaming spinner status is missing actions left group.');
    }
    return resolveDirectChild(left, predicate);
};

const resolveStreamingStatusElement = (actionsElement: HTMLElement): HTMLElement | null => {
    return resolveActionFlowChild(actionsElement, isStatusElement);
};

const resolveOwningMessageRoot = (statusElement: HTMLElement): HTMLElement => {
    const messageRoot = statusElement.closest('.chat-message[data-id]');
    if (!isHTMLElement(messageRoot)) {
        throw new Error('Streaming spinner status is missing owning chat message.');
    }
    return messageRoot;
};

const resolveMessageId = (messageRoot: HTMLElement): string => {
    const messageId = normalizeMessageDomId(messageRoot.getAttribute('data-id') ?? '');
    if (!messageId) {
        throw new Error('Streaming spinner status is missing message id.');
    }
    return messageId;
};

const requireStatusTextElement = (statusElement: HTMLElement): HTMLElement => {
    const candidate = resolveDirectChild(statusElement, isStatusTextElement);
    if (!isHTMLElement(candidate)) {
        throw new Error('Streaming spinner status is missing required text element.');
    }
    return candidate;
};

const requireStatusTextBodyElement = (labelElement: HTMLElement): HTMLElement => {
    const candidate = resolveDirectChild(labelElement, isStatusTextBodyElement);
    if (!isHTMLElement(candidate)) {
        throw new Error('Streaming spinner status is missing required text body element.');
    }
    return candidate;
};

const resolveActionsElement = (statusElement: HTMLElement): HTMLElement => {
    const actionsElement = statusElement.closest('.message-actions');
    if (!isHTMLElement(actionsElement)) {
        throw new Error('Streaming spinner status is missing actions container.');
    }
    return actionsElement;
};

const resolveSpinnerElement = (actionsElement: HTMLElement): HTMLElement | null => {
    const candidate = resolveActionFlowChild(actionsElement, isSpinnerElement);
    return isHTMLElement(candidate) ? candidate : null;
};

const hasVisibleSpinnerActivity = (messageRoot: HTMLElement): boolean => {
    const actionsElement = resolveMessageActionsElement(messageRoot);
    return readBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE) || readBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE);
};

const hasRunningLoadingActivity = (messageRoot: HTMLElement): boolean => {
    return readBooleanAttribute(resolveMessageActionsElement(messageRoot), STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE);
};

const hasRunningWaitActivity = (messageRoot: HTMLElement): boolean => {
    return readBooleanAttribute(resolveMessageActionsElement(messageRoot), STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE);
};

const hasRunningContextCompactionActivity = (messageRoot: HTMLElement): boolean => {
    return readBooleanAttribute(resolveMessageActionsElement(messageRoot), STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE);
};

const hasSettledActionButtons = (actionsElement: HTMLElement): boolean => {
    const actionButtons = resolveDirectChild(actionsElement, isSettledActionButtonsElement);
    return actionButtons instanceof HTMLElement && hasActiveActionButtonDescendant(actionButtons);
};

const hasActiveMessageActionButton = (actionsElement: HTMLElement): boolean => {
    if (actionsElement.getAttribute('data-user-input-required') === 'true') {
        return false;
    }
    const actionButtons = resolveDirectChild(actionsElement, isSettledActionButtonsElement);
    return actionButtons instanceof HTMLElement && hasActiveActionButtonDescendant(actionButtons);
};

export { hasActiveMessageActionButton, hasRunningContextCompactionActivity, hasRunningLoadingActivity, hasRunningWaitActivity, hasSettledActionButtons, hasVisibleSpinnerActivity, requireStatusTextBodyElement, requireStatusTextElement, resolveActionsElement, resolveMessageActionsElement, resolveMessageId, resolveOwningMessageRoot, resolveSpinnerElement, resolveStreamingStatusElement };
