/* SoAI - Assistant message action DOM patching [frontend/assets/ts/features/chat/message/assistantMessageActionsPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { STREAMING_ACTION_CONTROLS_CLASS } from '@features/chat/message/messageActionStreamingPolicy.ts';
import { exitWithPresence, insertWithPresence, isPresenceExiting, prepareEnterWithPresence, removeWithPresence, stopPresenceAnimation } from '@core/animations/presence/public.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { cancelSpinnerStatusTerminalTransition, deferSettledActionsUntilSpinnerExit, isSpinnerStatusTerminalTransitionActive } from '@features/chat/stream/streamMessageSpinnerStatusTerminalReconcile.ts';
import { patchMessageActionButtons } from '@features/chat/message/assistantMessageActionButtonPatching.ts';
import { patchAssistantActionButtons, requireAssistantActionButtonGroups, resolveAssistantActionFlowChildren } from '@features/chat/message/assistantMessageActionLayoutPatching.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { hasStreamingAssistantDom } from '@features/chat/message/assistantStreamingDomState.ts';
import type { ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { requireStatusTextBodyElement, requireStatusTextElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { FIRST_REVEAL_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { clearSpinnerStatusRuntimeText } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';

const MESSAGE_ACTION_BUTTONS_CLASS = 'message-action-buttons';
const STREAMING_ACTION_RUNTIME_ATTRIBUTE_NAMES: ReadonlySet<string> = new Set([FIRST_REVEAL_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE]);

type AssistantMessageActionsChildren = {
    buttons: HTMLElement | null;
};

const resolveAssistantMessageActionsChildren = (actions: HTMLElement, includeExiting = false): AssistantMessageActionsChildren => {
    const resolved: AssistantMessageActionsChildren = {
        buttons: null
    };
    for (const child of Array.from(actions.children)) {
        if (!(child instanceof HTMLElement) || (!includeExiting && isPresenceExiting(child))) {
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
    if (isSpinnerStatusTerminalTransitionActive(actions)) return false;
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
    if (groups.left.classList.contains(STREAMING_ACTION_CONTROLS_CLASS)) return false;
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

const hasSettledMessageControls = (buttons: HTMLElement): boolean => {
    const group = requireAssistantActionButtonGroups(buttons).left;
    return !group.classList.contains(STREAMING_ACTION_CONTROLS_CLASS) && Array.from(group.children).some((element) => element.classList.contains('message-action') && !isPresenceExiting(element));
};

const patchAssistantMessageActionsInPlace = (existingActions: HTMLElement, createdActions: HTMLElement, options: ChatMessageInsertAnimationOptions = {}): boolean => {
    if (isStreamingActionsElement(createdActions)) cancelSpinnerStatusTerminalTransition(existingActions);
    else if ((isStreamingActionsElement(existingActions) || isSpinnerStatusTerminalTransitionActive(existingActions)) && deferSettledActionsUntilSpinnerExit(existingActions, () => patchAssistantMessageActionsInPlace(existingActions, createdActions, { ...options, suppressInsertAnimations: true }))) return true;
    const completingStream = isStreamingActionsElement(existingActions) && !isStreamingActionsElement(createdActions);
    const startingStream = !isStreamingActionsElement(existingActions) && isStreamingActionsElement(createdActions);
    const existingChildren = resolveAssistantMessageActionsChildren(existingActions, true);
    const createdChildren = resolveAssistantMessageActionsChildren(createdActions);
    const existingButtons = existingChildren.buttons;
    const createdButtons = createdChildren.buttons;
    const revealingSettledControls = !isStreamingActionsElement(createdActions) && existingButtons !== null && createdButtons !== null && requiresAssistantActionLayoutPatching(existingButtons, createdButtons) && !hasSettledMessageControls(existingButtons) && hasSettledMessageControls(createdButtons);
    const preservedAttributeNames = resolveActionRuntimeAttributePreservation(existingActions, createdActions);
    const preserveRuntimeStatusText = preservedAttributeNames !== undefined;
    if (startingStream && existingButtons && requiresAssistantActionLayoutPatching(existingButtons, existingButtons)) {
        const group = requireAssistantActionButtonGroups(existingButtons).left;
        const view = existingActions.ownerDocument.defaultView;
        if (view === null) throw new Error('Streaming controls require their owning window.');
        const groupOpacity = Number(view.getComputedStyle(group).opacity);
        stopPresenceAnimation(group);
        for (const control of group.children) {
            if (!(control instanceof HTMLElement) || !control.classList.contains('message-action')) continue;
            const fromOpacity = groupOpacity * Number(view.getComputedStyle(control).opacity);
            control.setAttribute('data-presence-visual-only', '');
            exitWithPresence(control, null, () => control.removeAttribute('data-presence-visual-only'), { fromOpacity });
        }
    }
    let changed = preservedAttributeNames ? syncElementShell({ target: existingActions, source: createdActions, preservedAttributeNames }) : syncElementShell({ target: existingActions, source: createdActions });
    const patchOptions = completingStream || revealingSettledControls ? { ...options, suppressInsertAnimations: true } : options;
    if (existingButtons && createdButtons && isPresenceExiting(existingButtons)) {
        insertWithPresence(existingActions, existingButtons);
        changed = true;
    }
    if (existingButtons && createdButtons && (requiresAssistantActionLayoutPatching(existingButtons, createdButtons) ? patchAssistantActionButtons(existingButtons, createdButtons, patchOptions, preserveRuntimeStatusText) : patchMessageActionButtons(existingButtons, createdButtons, options))) {
        changed = true;
    } else if (existingButtons && !createdButtons) {
        if (!isPresenceExiting(existingButtons)) {
            removeWithPresence(existingButtons);
            changed = true;
        }
    } else if (!existingButtons && createdButtons) {
        const inserted = createdButtons.cloneNode(true);
        if (!(inserted instanceof HTMLElement)) {
            throw new Error('Assistant message action patch failed to clone action buttons.');
        }
        insertWithPresence(existingActions, inserted, null, options.suppressInsertAnimations !== true);
        changed = true;
    }
    if ((completingStream || revealingSettledControls) && existingButtons && createdButtons && requiresAssistantActionLayoutPatching(existingButtons, createdButtons)) {
        prepareEnterWithPresence(requireAssistantActionButtonGroups(existingButtons).left, true, true)();
    }
    return changed;
};

export { hasSettledAssistantActionsChrome, normalizeSettledAssistantActionsChrome, patchAssistantMessageActionsInPlace };
