/* SoAI - Assistant message action DOM patching [frontend/assets/ts/features/chat/message/assistantMessageActionsPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncElementShell } from '@core/dom/patching.ts';
import { patchMessageActionButtons } from '@features/chat/message/assistantMessageActionButtonPatching.ts';
import { patchAssistantActionButtons, requireAssistantActionButtonGroups, resolveAssistantActionFlowChildren } from '@features/chat/message/assistantMessageActionLayoutPatching.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { hasStreamingAssistantDom } from '@features/chat/message/assistantStreamingDomState.ts';
import { applyChatMessageActionButtonsEnterAnimation, type ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { requireStatusTextBodyElement, requireStatusTextElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { FIRST_REVEAL_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { clearSpinnerStatusRuntimeText } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';

const MESSAGE_ACTION_BUTTONS_CLASS = 'message-action-buttons';
const STREAMING_ACTION_RUNTIME_ATTRIBUTE_NAMES: ReadonlySet<string> = new Set([FIRST_REVEAL_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE]);

type AssistantMessageActionsChildren = {
    buttons: HTMLElement | null;
};

const resolveAssistantMessageActionsChildren = (actions: HTMLElement): AssistantMessageActionsChildren => {
    const resolved: AssistantMessageActionsChildren = {
        buttons: null
    };
    for (const child of Array.from(actions.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (resolved.buttons === null && child.classList.contains(MESSAGE_ACTION_BUTTONS_CLASS)) {
            resolved.buttons = child;
        }
    }
    return resolved;
};

const isStreamingActionsElement = (element: HTMLElement): boolean => {
    return element.getAttribute('data-message-streaming') === 'true';
};

const normalizeSettledAssistantActionsElement = (actions: HTMLElement): boolean => {
    let changed = false;
    if (actions.getAttribute('data-message-streaming') !== 'false') {
        actions.setAttribute('data-message-streaming', 'false');
        changed = true;
    }
    if (actions.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) !== 'false') {
        actions.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'false');
        changed = true;
    }
    if (actions.hasAttribute(FIRST_REVEAL_ATTRIBUTE)) {
        actions.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        changed = true;
    }
    const buttons = resolveAssistantMessageActionsChildren(actions).buttons;
    const groups = buttons === null ? null : requireAssistantActionButtonGroups(buttons);
    const status = groups === null ? null : resolveAssistantActionFlowChildren(groups.left, groups.right).status;
    if (status !== null) {
        const label = requireStatusTextElement(status);
        const body = requireStatusTextBodyElement(label);
        if (clearSpinnerStatusRuntimeText(status, label, body, actions)) {
            changed = true;
        }
    }
    return changed;
};

const normalizeSettledAssistantActionsChrome = (root: HTMLElement): boolean => {
    const actions = resolveAssistantMessageParts(root)?.actions ?? null;
    return actions === null ? false : normalizeSettledAssistantActionsElement(actions);
};

const hasSettledAssistantActionsChrome = (root: HTMLElement): boolean => {
    if (hasStreamingAssistantDom(root)) {
        return false;
    }
    const actions = resolveAssistantMessageParts(root)?.actions ?? null;
    if (actions === null || actions.getAttribute('data-message-streaming') !== 'false') {
        return false;
    }
    if (actions.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) !== 'false' || actions.hasAttribute(FIRST_REVEAL_ATTRIBUTE)) {
        return false;
    }
    const children = resolveAssistantMessageActionsChildren(actions);
    if (children.buttons === null) {
        return false;
    }
    const groups = requireAssistantActionButtonGroups(children.buttons);
    const status = resolveAssistantActionFlowChildren(groups.left, groups.right).status;
    if (status === null) {
        return true;
    }
    const label = requireStatusTextElement(status);
    const body = requireStatusTextBodyElement(label);
    return body.getAttribute('data-stream-spinner-text-value') === '' && body.textContent === '';
};

const resolveActionRuntimeAttributePreservation = (existingActions: HTMLElement, createdActions: HTMLElement): ReadonlySet<string> | undefined => {
    return isStreamingActionsElement(existingActions) && isStreamingActionsElement(createdActions) ? STREAMING_ACTION_RUNTIME_ATTRIBUTE_NAMES : undefined;
};

const requiresAssistantActionLayoutPatching = (existingButtons: HTMLElement, createdButtons: HTMLElement): boolean => {
    return existingButtons.classList.contains('message-action-buttons--assistant') || createdButtons.classList.contains('message-action-buttons--assistant');
};

const patchAssistantMessageActionsInPlace = (existingActions: HTMLElement, createdActions: HTMLElement, options: ChatMessageInsertAnimationOptions = {}): boolean => {
    const preservedAttributeNames = resolveActionRuntimeAttributePreservation(existingActions, createdActions);
    const preserveRuntimeStatusText = preservedAttributeNames !== undefined;
    let changed = preservedAttributeNames ? syncElementShell({ target: existingActions, source: createdActions, preservedAttributeNames }) : syncElementShell({ target: existingActions, source: createdActions });
    const existingChildren = resolveAssistantMessageActionsChildren(existingActions);
    const createdChildren = resolveAssistantMessageActionsChildren(createdActions);
    const existingButtons = existingChildren.buttons;
    const createdButtons = createdChildren.buttons;
    if (existingButtons && createdButtons && (requiresAssistantActionLayoutPatching(existingButtons, createdButtons) ? patchAssistantActionButtons(existingButtons, createdButtons, options, preserveRuntimeStatusText) : patchMessageActionButtons(existingButtons, createdButtons, options))) {
        changed = true;
    } else if (existingButtons && !createdButtons) {
        existingButtons.remove();
        changed = true;
    } else if (!existingButtons && createdButtons) {
        const inserted = createdButtons.cloneNode(true);
        if (!(inserted instanceof HTMLElement)) {
            throw new Error('Assistant message action patch failed to clone action buttons.');
        }
        existingActions.appendChild(inserted);
        applyChatMessageActionButtonsEnterAnimation(inserted, options);
        changed = true;
    }
    return changed;
};

export { hasSettledAssistantActionsChrome, normalizeSettledAssistantActionsChrome, patchAssistantMessageActionsInPlace };
