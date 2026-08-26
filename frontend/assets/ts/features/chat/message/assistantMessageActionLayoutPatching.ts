/* SoAI - Assistant message action row layout patching [frontend/assets/ts/features/chat/message/assistantMessageActionLayoutPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { patchMessageActionButtonGroup } from '@features/chat/message/assistantMessageActionButtonPatching.ts';
import { applyChatMessageEnterAnimation, type ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE } from '@features/chat/message/messageRunningActivitySummaryMarkup.ts';
import { requireStatusTextBodyElement, requireStatusTextElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';

const MESSAGE_ACTION_BUTTONS_LEFT_CLASS = 'message-action-buttons-left';
const MESSAGE_ACTION_BUTTONS_RIGHT_CLASS = 'message-action-buttons-right';
const MESSAGE_STREAMING_STATUS_CLASS = 'message-streaming-status';
const MESSAGE_STREAMING_SPINNER_CLASS = 'message-streaming-spinner-indicator';

type AssistantActionButtonGroups = {
    left: HTMLElement;
    right: HTMLElement;
};

type AssistantActionFlowChildren = {
    spinner: HTMLElement | null;
    status: HTMLElement | null;
    summary: HTMLElement | null;
};

type StreamingStatusPatchOptions = {
    preserveRuntimeText: boolean;
};

const isStreamingSpinnerElement = (element: HTMLElement): boolean => {
    return element.classList.contains('loading-spinner') && element.classList.contains(MESSAGE_STREAMING_SPINNER_CLASS);
};

const isStreamingStatusElement = (element: HTMLElement): boolean => {
    return element.classList.contains(MESSAGE_STREAMING_STATUS_CLASS);
};

const isRunningActivitySummaryElement = (element: HTMLElement): boolean => {
    return element.getAttribute(RUNNING_ACTIVITY_SUMMARY_ATTRIBUTE) === 'true';
};

const requireAssistantActionButtonGroups = (buttons: HTMLElement): AssistantActionButtonGroups => {
    let left: HTMLElement | null = null;
    let right: HTMLElement | null = null;
    for (const child of Array.from(buttons.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (left === null && child.classList.contains(MESSAGE_ACTION_BUTTONS_LEFT_CLASS)) {
            left = child;
            continue;
        }
        if (right === null && child.classList.contains(MESSAGE_ACTION_BUTTONS_RIGHT_CLASS)) {
            right = child;
        }
    }
    if (left === null || right === null) {
        throw new Error('Assistant message action patch requires canonical assistant action groups.');
    }
    return { left, right };
};

const resolveAssistantActionFlowChildren = (left: HTMLElement, right: HTMLElement): AssistantActionFlowChildren => {
    let spinner: HTMLElement | null = null;
    let status: HTMLElement | null = null;
    let summary: HTMLElement | null = null;
    for (const child of Array.from(left.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (spinner === null && isStreamingSpinnerElement(child)) {
            spinner = child;
            continue;
        }
        if (status === null && isStreamingStatusElement(child)) {
            status = child;
            continue;
        }
        if (summary === null && isRunningActivitySummaryElement(child)) {
            summary = child;
        }
    }
    for (const child of Array.from(right.children)) {
        if (child instanceof HTMLElement && summary === null && isRunningActivitySummaryElement(child)) {
            summary = child;
        }
    }
    return { spinner, status, summary };
};

const patchSimpleActionNode = (existingNode: HTMLElement, createdNode: HTMLElement): boolean => {
    let changed = syncElementShell({ target: existingNode, source: createdNode });
    if (replaceChildrenIfChanged(existingNode, createdNode)) {
        changed = true;
    }
    return changed;
};

const requireCanonicalStreamingStatusLabel = (label: HTMLElement): void => {
    requireStatusTextBodyElement(label);
    if (label.children.length !== 1) {
        throw new Error('Assistant message action patch requires canonical streaming status text.');
    }
};

const patchStreamingStatusTextBody = (existingLabel: HTMLElement, createdLabel: HTMLElement): boolean => {
    const existingBody = requireStatusTextBodyElement(existingLabel);
    const createdBody = requireStatusTextBodyElement(createdLabel);
    return patchSimpleActionNode(existingBody, createdBody);
};

const patchStreamingStatusNode = (existingStatus: HTMLElement, createdStatus: HTMLElement, options: StreamingStatusPatchOptions): boolean => {
    let changed = syncElementShell({ target: existingStatus, source: createdStatus });
    const existingLabel = requireStatusTextElement(existingStatus);
    const createdLabel = requireStatusTextElement(createdStatus);
    if (syncElementShell({ target: existingLabel, source: createdLabel })) {
        changed = true;
    }
    requireCanonicalStreamingStatusLabel(existingLabel);
    requireCanonicalStreamingStatusLabel(createdLabel);
    if (!options.preserveRuntimeText && patchStreamingStatusTextBody(existingLabel, createdLabel)) {
        changed = true;
    }
    return changed;
};

const patchAssistantActionFlowNode = (inputArguments: { existingParent: HTMLElement; existingNode: HTMLElement | null; createdNode: HTMLElement | null; beforeNode: ChildNode | null; cloneError: string; options: ChatMessageInsertAnimationOptions; patchNode: (existingNode: HTMLElement, createdNode: HTMLElement) => boolean }): boolean => {
    const { existingParent, existingNode, createdNode, beforeNode, cloneError, options, patchNode } = inputArguments;
    if (existingNode && createdNode) {
        let changed = patchNode(existingNode, createdNode);
        if (existingNode.parentElement !== existingParent) {
            existingParent.insertBefore(existingNode, beforeNode);
            changed = true;
        }
        return changed;
    }
    if (existingNode && !createdNode) {
        existingNode.remove();
        return true;
    }
    if (!existingNode && createdNode) {
        const inserted = createdNode.cloneNode(true);
        if (!(inserted instanceof HTMLElement)) {
            throw new Error(cloneError);
        }
        applyChatMessageEnterAnimation(inserted, options);
        existingParent.insertBefore(inserted, beforeNode);
        return true;
    }
    return false;
};

const patchAssistantActionButtons = (existingButtons: HTMLElement, createdButtons: HTMLElement, options: ChatMessageInsertAnimationOptions, preserveRuntimeStatusText: boolean): boolean => {
    let changed = syncElementShell({ target: existingButtons, source: createdButtons });
    const existingGroups = requireAssistantActionButtonGroups(existingButtons);
    const createdGroups = requireAssistantActionButtonGroups(createdButtons);
    const existingChildren = resolveAssistantActionFlowChildren(existingGroups.left, existingGroups.right);
    const createdChildren = resolveAssistantActionFlowChildren(createdGroups.left, createdGroups.right);
    if (syncElementShell({ target: existingGroups.left, source: createdGroups.left })) {
        changed = true;
    }
    if (syncElementShell({ target: existingGroups.right, source: createdGroups.right })) {
        changed = true;
    }
    const resolvedButtonAnchor = dom.resolve('.message-action', existingGroups.left);
    const buttonAnchor = resolvedButtonAnchor instanceof HTMLElement ? resolvedButtonAnchor : null;
    if (
        patchAssistantActionFlowNode({
            existingParent: existingGroups.left,
            existingNode: existingChildren.spinner,
            createdNode: createdChildren.spinner,
            beforeNode: existingChildren.status ?? existingGroups.left.firstChild,
            cloneError: 'Assistant message action patch failed to clone streaming spinner.',
            options,
            patchNode: patchSimpleActionNode
        })
    ) {
        changed = true;
    }
    if (
        patchAssistantActionFlowNode({
            existingParent: existingGroups.left,
            existingNode: existingChildren.status,
            createdNode: createdChildren.status,
            beforeNode: buttonAnchor,
            cloneError: 'Assistant message action patch failed to clone streaming status.',
            options,
            patchNode: (existingNode, createdNode) => patchStreamingStatusNode(existingNode, createdNode, { preserveRuntimeText: preserveRuntimeStatusText })
        })
    ) {
        changed = true;
    }
    if (patchMessageActionButtonGroup(existingGroups.left, createdGroups.left, options, (element) => isStreamingSpinnerElement(element) || isStreamingStatusElement(element) || isRunningActivitySummaryElement(element))) {
        changed = true;
    }
    if (
        patchAssistantActionFlowNode({
            existingParent: existingGroups.left,
            existingNode: existingChildren.summary,
            createdNode: createdChildren.summary,
            beforeNode: null,
            cloneError: 'Assistant message action patch failed to clone running activity summary.',
            options,
            patchNode: patchSimpleActionNode
        })
    ) {
        changed = true;
    }
    if (patchMessageActionButtonGroup(existingGroups.right, createdGroups.right, options, isRunningActivitySummaryElement)) {
        changed = true;
    }
    return changed;
};

export { isRunningActivitySummaryElement, isStreamingSpinnerElement, isStreamingStatusElement, patchAssistantActionButtons, requireAssistantActionButtonGroups, resolveAssistantActionFlowChildren };
