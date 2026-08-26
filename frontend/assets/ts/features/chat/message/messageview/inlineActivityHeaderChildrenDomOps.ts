/* SoAI - Chat feature inline activity header children DOM ops [frontend/assets/ts/features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveHTMLElement } from '@core/dom/patching.ts';

const LEADING_ICON_CLASS = 'inline-activity-leading-icon';
const STATUS_LED_CLASS = 'inline-activity-status-led';
const ICON_CLASS = 'inline-activity-icon';
const NAME_CLASS = 'inline-activity-name';
const SEPARATOR_DOT_CLASS = 'inline-activity-separator-dot';
const PREVIEW_CLASS = 'inline-activity-preview';
const DURATION_CLASS = 'inline-activity-duration';
const STOP_BUTTON_CLASS = 'inline-activity-stop-button';
const CLOSE_BUTTON_CLASS = 'inline-activity-close-button';
const INLINE_ACTIVITY_CLASS = 'inline-activity';
const ASSISTANT_ROLE_ACTIVITY_CLASS = 'message-role-activity';
const ASSISTANT_RESPONSE_DURATION_ATTRIBUTE = 'data-assistant-response-duration';

type InlineActivityHeaderChildren = {
    stopButton: HTMLElement | null;
    closeButton: HTMLElement | null;
    leadingIcon: HTMLElement | null;
    statusLed: HTMLElement | null;
    icon: HTMLElement | null;
    name: HTMLElement | null;
    separatorDot: HTMLElement | null;
    preview: HTMLElement | null;
    duration: HTMLElement | null;
};

const isAssistantRoleActivityHeader = (header: HTMLElement): boolean => {
    const parent = header.parentElement;
    return parent instanceof HTMLElement && parent.classList.contains(INLINE_ACTIVITY_CLASS) && parent.classList.contains(ASSISTANT_ROLE_ACTIVITY_CLASS);
};

const isHeaderOwnedDurationNode = (header: HTMLElement, node: HTMLElement): boolean => {
    const isAssistantDuration = node.hasAttribute(ASSISTANT_RESPONSE_DURATION_ATTRIBUTE);
    return isAssistantRoleActivityHeader(header) ? isAssistantDuration : !isAssistantDuration;
};

const resolveInlineActivityHeader = (activity: HTMLElement): HTMLElement | null => {
    return resolveHTMLElement(':scope > .inline-activity-header', activity);
};

const resolveInlineActivityPreviewText = (preview: HTMLElement): HTMLElement | null => {
    return resolveHTMLElement(':scope > .inline-activity-preview-text', preview);
};

const removeUnownedHeaderDurationNodes = (header: HTMLElement, primaryDuration: HTMLElement | null): boolean => {
    let changed = false;
    for (const child of Array.from(header.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains(DURATION_CLASS) || child === primaryDuration) {
            continue;
        }
        if (isHeaderOwnedDurationNode(header, child)) {
            continue;
        }
        child.remove();
        changed = true;
    }
    return changed;
};

const resolveHeaderChildren = (header: HTMLElement): InlineActivityHeaderChildren => {
    const resolved: InlineActivityHeaderChildren = {
        stopButton: null,
        closeButton: null,
        leadingIcon: null,
        statusLed: null,
        icon: null,
        name: null,
        separatorDot: null,
        preview: null,
        duration: null
    };
    for (const child of Array.from(header.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (resolved.stopButton === null && child.classList.contains(STOP_BUTTON_CLASS)) {
            resolved.stopButton = child;
            continue;
        }
        if (resolved.closeButton === null && child.classList.contains(CLOSE_BUTTON_CLASS)) {
            resolved.closeButton = child;
            continue;
        }
        if (resolved.leadingIcon === null && child.classList.contains(LEADING_ICON_CLASS)) {
            resolved.leadingIcon = child;
            continue;
        }
        if (resolved.statusLed === null && child.classList.contains(STATUS_LED_CLASS)) {
            resolved.statusLed = child;
            continue;
        }
        if (resolved.icon === null && child.classList.contains(ICON_CLASS)) {
            resolved.icon = child;
            continue;
        }
        if (resolved.name === null && child.classList.contains(NAME_CLASS)) {
            resolved.name = child;
            continue;
        }
        if (resolved.separatorDot === null && child.classList.contains(SEPARATOR_DOT_CLASS)) {
            resolved.separatorDot = child;
            continue;
        }
        if (resolved.preview === null && child.classList.contains(PREVIEW_CLASS)) {
            resolved.preview = child;
            continue;
        }
        if (resolved.duration === null && child.classList.contains(DURATION_CLASS) && isHeaderOwnedDurationNode(header, child)) {
            resolved.duration = child;
        }
    }
    return resolved;
};

const resolveFirstHeaderActionButton = (header: HTMLElement): HTMLElement | null => {
    const children = resolveHeaderChildren(header);
    return children.stopButton ?? children.closeButton;
};

const insertBeforeHeaderActions = (header: HTMLElement, node: Node): void => {
    const actionButton = resolveFirstHeaderActionButton(header);
    if (actionButton) {
        header.insertBefore(node, actionButton);
        return;
    }
    header.appendChild(node);
};

const isElementAfterAnchor = (parent: HTMLElement, element: HTMLElement, anchor: HTMLElement): boolean => {
    const children = Array.from(parent.children);
    return children.indexOf(element) > children.indexOf(anchor);
};

const moveBeforeAnchorIfAfter = (header: HTMLElement, node: HTMLElement | null, anchor: HTMLElement): boolean => {
    if (!node || !isElementAfterAnchor(header, node, anchor)) {
        return false;
    }
    header.insertBefore(node, anchor);
    return true;
};

export { insertBeforeHeaderActions, isHeaderOwnedDurationNode, moveBeforeAnchorIfAfter, removeUnownedHeaderDurationNodes, resolveHeaderChildren, resolveInlineActivityHeader, resolveInlineActivityPreviewText };
export type { InlineActivityHeaderChildren };
