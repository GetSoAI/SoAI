/* SoAI - Chat feature inline activity header children patching [frontend/assets/ts/features/chat/message/messageview/inlineActivityHeaderChildrenPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { haveEqualChildNodes, syncAttribute, syncAttributes, syncClass } from '@core/dom/patching.ts';
import { reapplyInlineActivityDetailsPendingChrome } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { patchInlineActivityPreviewNode } from '@features/chat/message/messageview/inlineActivityPreviewPatching.ts';
import { insertBeforeHeaderActions, moveBeforeAnchorIfAfter, removeUnownedHeaderDurationNodes, resolveHeaderChildren } from '@features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts';

const INLINE_ACTIVITY_STOP_REQUESTED_ATTRIBUTE = 'data-inline-activity-stop-requested';

const syncHeaderChildNode = (inputArguments: { existingHeader: HTMLElement; existingNode: HTMLElement | null; createdNode: HTMLElement | null; anchor: HTMLElement | null }): boolean => {
    const existingNode = inputArguments.existingNode;
    const createdNode = inputArguments.createdNode;
    if (!createdNode) {
        if (!existingNode) {
            return false;
        }
        existingNode.remove();
        return true;
    }
    if (!existingNode) {
        const cloned = createdNode.cloneNode(true);
        if (inputArguments.anchor) {
            inputArguments.existingHeader.insertBefore(cloned, inputArguments.anchor);
            return true;
        }
        inputArguments.existingHeader.appendChild(cloned);
        return true;
    }
    let changed = false;
    if (syncClass(existingNode, createdNode)) {
        changed = true;
    }
    if (syncAttributes({ target: existingNode, source: createdNode })) {
        changed = true;
    }
    if (!haveEqualChildNodes(existingNode, createdNode)) {
        existingNode.textContent = '';
        for (const node of Array.from(createdNode.childNodes)) {
            existingNode.appendChild(node.cloneNode(true));
        }
        changed = true;
    }
    return changed;
};

const patchDurationNode = (existingHeader: HTMLElement, createdHeader: HTMLElement): boolean => {
    const existingDuration = resolveHeaderChildren(existingHeader).duration;
    const createdDuration = resolveHeaderChildren(createdHeader).duration;
    let changed = removeUnownedHeaderDurationNodes(existingHeader, existingDuration);
    if (!createdDuration) {
        if (!existingDuration) {
            return changed;
        }
        existingDuration.remove();
        return true;
    }
    if (!existingDuration) {
        insertBeforeHeaderActions(existingHeader, createdDuration.cloneNode(true));
        return true;
    }
    if (existingDuration.textContent !== createdDuration.textContent) {
        existingDuration.textContent = createdDuration.textContent;
        changed = true;
    }
    if (syncClass(existingDuration, createdDuration)) {
        changed = true;
    }
    if (syncAttributes({ target: existingDuration, source: createdDuration })) {
        changed = true;
    }
    return changed;
};

const patchInlineActivityHeaderChildrenInPlace = (existingHeader: HTMLElement, createdHeader: HTMLElement): boolean => {
    let changed = false;
    if (syncClass(existingHeader, createdHeader)) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'data-action' })) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'data-call-id' })) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'aria-disabled' })) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'data-toggle-disabled' })) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'data-tooltip' })) {
        changed = true;
    }
    if (syncAttribute({ target: existingHeader, source: createdHeader, name: 'aria-label' })) {
        changed = true;
    }
    const existingChildren = resolveHeaderChildren(existingHeader);
    const createdChildren = resolveHeaderChildren(createdHeader);
    const name = existingChildren.name;
    if (syncHeaderChildNode({ existingHeader, existingNode: existingChildren.leadingIcon, createdNode: createdChildren.leadingIcon, anchor: existingChildren.statusLed ?? existingChildren.icon ?? name })) {
        changed = true;
    }
    const existingStatusLed = existingChildren.statusLed;
    const createdStatusLed = createdChildren.statusLed;
    if (createdStatusLed && existingStatusLed) {
        if (syncClass(existingStatusLed, createdStatusLed)) {
            changed = true;
        }
        if (syncAttributes({ target: existingStatusLed, source: createdStatusLed })) {
            changed = true;
        }
    } else if (createdStatusLed) {
        const existingIcon = resolveHeaderChildren(existingHeader).icon;
        const anchor = existingIcon ?? name;
        const cloned = createdStatusLed.cloneNode(true);
        if (anchor) {
            existingHeader.insertBefore(cloned, anchor);
        } else {
            existingHeader.appendChild(cloned);
        }
        changed = true;
    } else if (existingStatusLed) {
        existingStatusLed.remove();
        changed = true;
    }
    if (syncHeaderChildNode({ existingHeader, existingNode: existingChildren.icon, createdNode: createdChildren.icon, anchor: name })) {
        changed = true;
    }
    const existingName = existingChildren.name;
    const createdName = createdChildren.name;
    if (createdName && existingName) {
        if (syncClass(existingName, createdName)) {
            changed = true;
        }
        if (syncAttributes({ target: existingName, source: createdName })) {
            changed = true;
        }
        if (existingName.textContent !== createdName.textContent) {
            existingName.textContent = createdName.textContent;
            changed = true;
        }
    } else if (createdName) {
        const currentChildren = resolveHeaderChildren(existingHeader);
        const separatorDot = currentChildren.separatorDot;
        const preview = currentChildren.preview;
        const duration = currentChildren.duration;
        const anchor = separatorDot ?? preview ?? duration ?? null;
        const cloned = createdName.cloneNode(true);
        if (anchor) {
            existingHeader.insertBefore(cloned, anchor);
        } else {
            existingHeader.appendChild(cloned);
        }
        changed = true;
    } else if (existingName) {
        existingName.remove();
        changed = true;
    }
    const existingSeparatorDot = existingChildren.separatorDot;
    const createdSeparatorDot = createdChildren.separatorDot;
    if (createdSeparatorDot && existingSeparatorDot) {
        if (syncClass(existingSeparatorDot, createdSeparatorDot)) {
            changed = true;
        }
        if (syncAttributes({ target: existingSeparatorDot, source: createdSeparatorDot })) {
            changed = true;
        }
    } else if (createdSeparatorDot) {
        insertBeforeHeaderActions(existingHeader, createdSeparatorDot.cloneNode(true));
        changed = true;
    } else if (existingSeparatorDot) {
        existingSeparatorDot.remove();
        changed = true;
    }
    if (patchInlineActivityPreviewNode(existingHeader, createdHeader)) {
        changed = true;
    }
    if (patchDurationNode(existingHeader, createdHeader)) {
        changed = true;
    }
    const activity = existingHeader.closest('.inline-activity');
    const stopRequested = activity instanceof HTMLElement && activity.getAttribute(INLINE_ACTIVITY_STOP_REQUESTED_ATTRIBUTE) === 'true';
    const createdStopButton = stopRequested ? null : createdChildren.stopButton;
    const actionChildren = resolveHeaderChildren(existingHeader);
    if (syncHeaderChildNode({ existingHeader, existingNode: actionChildren.stopButton, createdNode: createdStopButton, anchor: actionChildren.closeButton })) {
        changed = true;
    }
    const refreshedActionChildren = resolveHeaderChildren(existingHeader);
    if (syncHeaderChildNode({ existingHeader, existingNode: refreshedActionChildren.closeButton, createdNode: createdChildren.closeButton, anchor: null })) {
        changed = true;
    }
    if (activity instanceof HTMLElement) {
        reapplyInlineActivityDetailsPendingChrome(activity);
    }
    const finalChildren = resolveHeaderChildren(existingHeader);
    const separatorDot = finalChildren.separatorDot;
    const preview = finalChildren.preview;
    if (separatorDot && preview && separatorDot.nextSibling !== preview) {
        existingHeader.insertBefore(preview, separatorDot.nextSibling);
        changed = true;
    }
    const duration = finalChildren.duration;
    const stopButton = finalChildren.stopButton;
    const closeButton = finalChildren.closeButton;
    if (stopButton && closeButton && stopButton.nextSibling !== closeButton) {
        existingHeader.insertBefore(stopButton, closeButton);
        changed = true;
    }
    const firstActionButton = stopButton ?? closeButton;
    if (firstActionButton) {
        if (moveBeforeAnchorIfAfter(existingHeader, separatorDot, firstActionButton)) {
            changed = true;
        }
        if (moveBeforeAnchorIfAfter(existingHeader, preview, firstActionButton)) {
            changed = true;
        }
        if (moveBeforeAnchorIfAfter(existingHeader, duration, firstActionButton)) {
            changed = true;
        }
    }
    if (closeButton) {
        if (moveBeforeAnchorIfAfter(existingHeader, stopButton, closeButton)) {
            changed = true;
        }
    }
    return changed;
};

export { patchInlineActivityHeaderChildrenInPlace };
