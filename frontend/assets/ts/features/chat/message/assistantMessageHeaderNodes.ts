/* SoAI - Assistant message header element discovery [frontend/assets/ts/features/chat/message/assistantMessageHeaderNodes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AssistantHeaderRoleChildren = {
    comparisonNav: HTMLElement | null;
    assistantActivity: HTMLElement | null;
};

type ComparisonNavChildren = {
    assistantActivity: HTMLElement | null;
    previousButton: HTMLElement | null;
    nextButton: HTMLElement | null;
};

const MESSAGE_ROLE_CLASS = 'message-role';
const MESSAGE_ROLE_COMPARISON_NAV_CLASS = 'message-role-comparison-nav';
const ASSISTANT_ACTIVITY_CLASS = 'message-role-activity';
const COMPARISON_PREVIOUS_BUTTON_CLASS = 'chat-comparison-chevron--prev';
const COMPARISON_NEXT_BUTTON_CLASS = 'chat-comparison-chevron--next';

const resolveMessageRoleChild = (root: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && child.classList.contains(MESSAGE_ROLE_CLASS)) {
            return child;
        }
    }
    return null;
};

const resolveAssistantHeaderRoleChildren = (root: HTMLElement): AssistantHeaderRoleChildren => {
    const resolved: AssistantHeaderRoleChildren = {
        comparisonNav: null,
        assistantActivity: null
    };
    for (const child of Array.from(root.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (resolved.comparisonNav === null && child.classList.contains(MESSAGE_ROLE_COMPARISON_NAV_CLASS)) {
            resolved.comparisonNav = child;
            continue;
        }
        if (resolved.assistantActivity === null && child.classList.contains(ASSISTANT_ACTIVITY_CLASS)) {
            resolved.assistantActivity = child;
        }
    }
    return resolved;
};

const resolveComparisonNavChildren = (nav: HTMLElement): ComparisonNavChildren => {
    const resolved: ComparisonNavChildren = {
        assistantActivity: null,
        previousButton: null,
        nextButton: null
    };
    for (const child of Array.from(nav.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (resolved.assistantActivity === null && child.classList.contains(ASSISTANT_ACTIVITY_CLASS)) {
            resolved.assistantActivity = child;
            continue;
        }
        if (resolved.previousButton === null && child.classList.contains(COMPARISON_PREVIOUS_BUTTON_CLASS)) {
            resolved.previousButton = child;
            continue;
        }
        if (resolved.nextButton === null && child.classList.contains(COMPARISON_NEXT_BUTTON_CLASS)) {
            resolved.nextButton = child;
        }
    }
    return resolved;
};

export { resolveAssistantHeaderRoleChildren, resolveComparisonNavChildren, resolveMessageRoleChild };
