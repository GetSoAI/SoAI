/* SoAI - Chat feature assistant message header patching [frontend/assets/ts/features/chat/message/assistantMessageHeaderPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAttributes, syncClass } from '@core/dom/patching.ts';
import { patchElementChildren } from '@features/chat/message/assistantElementPatching.ts';
import { ASSISTANT_HEADER_ACTIVITY_STATUS_CLASSES, assistantHeaderActivityHasResponseLifecycleStatus } from '@features/chat/message/assistantHeaderCatalogStatus.ts';
import { resolveAssistantHeaderRoleChildren, resolveComparisonNavChildren, resolveMessageRoleChild } from '@features/chat/message/assistantMessageHeaderNodes.ts';
import { patchInlineActivityHeaderChildrenInPlace } from '@features/chat/message/messageview/inlineActivityHeaderChildrenPatching.ts';
import { resolveHeaderChildren, resolveInlineActivityHeader, resolveInlineActivityPreviewText } from '@features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts';

const syncHiddenState = (target: HTMLElement, source: HTMLElement): void => {
    target.hidden = source.hidden;
    if (source.hidden) {
        target.setAttribute('hidden', '');
        return;
    }
    target.removeAttribute('hidden');
};

const mergeAssistantHeaderActivityRealtimeState = (existingActivity: HTMLElement, createdActivity: HTMLElement): void => {
    if (!assistantHeaderActivityHasResponseLifecycleStatus(createdActivity)) {
        for (const statusClass of ASSISTANT_HEADER_ACTIVITY_STATUS_CLASSES) {
            createdActivity.classList.toggle(statusClass, existingActivity.classList.contains(statusClass));
        }
    }

    const existingHeader = resolveInlineActivityHeader(existingActivity);
    const createdHeader = resolveInlineActivityHeader(createdActivity);
    if (!existingHeader || !createdHeader) {
        return;
    }

    const existingHeaderChildren = resolveHeaderChildren(existingHeader);
    const createdHeaderChildren = resolveHeaderChildren(createdHeader);

    const existingPreview = existingHeaderChildren.preview;
    const createdPreview = createdHeaderChildren.preview;
    if (existingPreview && createdPreview) {
        syncHiddenState(createdPreview, existingPreview);
        const existingPreviewText = resolveInlineActivityPreviewText(existingPreview);
        const createdPreviewText = resolveInlineActivityPreviewText(createdPreview);
        if (existingPreviewText && createdPreviewText) {
            createdPreviewText.textContent = existingPreviewText.textContent;
        }
    }

    const existingSeparatorDot = existingHeaderChildren.separatorDot;
    const createdSeparatorDot = createdHeaderChildren.separatorDot;
    if (existingSeparatorDot && createdSeparatorDot) {
        syncHiddenState(createdSeparatorDot, existingSeparatorDot);
    }
};

const patchAssistantHeaderActivity = (existingActivity: HTMLElement, createdActivity: HTMLElement): boolean => {
    mergeAssistantHeaderActivityRealtimeState(existingActivity, createdActivity);
    const existingInlineHeader = resolveInlineActivityHeader(existingActivity);
    const createdInlineHeader = resolveInlineActivityHeader(createdActivity);
    if (!existingInlineHeader || !createdInlineHeader) {
        return false;
    }
    let changed = false;
    if (syncClass(existingActivity, createdActivity)) {
        changed = true;
    }
    if (syncAttributes({ target: existingActivity, source: createdActivity })) {
        changed = true;
    }
    if (patchInlineActivityHeaderChildrenInPlace(existingInlineHeader, createdInlineHeader)) {
        changed = true;
    }
    return changed;
};

const patchComparisonNavButton = (existingButton: HTMLElement | null, createdButton: HTMLElement | null): boolean | null => {
    if (!existingButton || !createdButton) {
        if (existingButton === null && createdButton === null) {
            return false;
        }
        return null;
    }
    return patchElementChildren(existingButton, createdButton);
};

const patchAssistantComparisonNav = (existingNav: HTMLElement, createdNav: HTMLElement): boolean | null => {
    let changed = false;
    if (syncClass(existingNav, createdNav)) {
        changed = true;
    }
    if (syncAttributes({ target: existingNav, source: createdNav })) {
        changed = true;
    }
    const existingChildren = resolveComparisonNavChildren(existingNav);
    const createdChildren = resolveComparisonNavChildren(createdNav);
    const existingActivity = existingChildren.assistantActivity;
    const createdActivity = createdChildren.assistantActivity;
    if (!existingActivity || !createdActivity) {
        return null;
    }
    if (patchAssistantHeaderActivity(existingActivity, createdActivity)) {
        changed = true;
    }
    const previousButtonChanged = patchComparisonNavButton(existingChildren.previousButton, createdChildren.previousButton);
    const nextButtonChanged = patchComparisonNavButton(existingChildren.nextButton, createdChildren.nextButton);
    if (previousButtonChanged === null || nextButtonChanged === null) {
        return null;
    }
    if (previousButtonChanged || nextButtonChanged) {
        changed = true;
    }
    return changed;
};

const patchAssistantRoleNodeStructure = (existingRole: HTMLElement, createdRole: HTMLElement): boolean => {
    return patchElementChildren(existingRole, createdRole);
};

const patchAssistantMessageRole = (existingRole: HTMLElement, createdRole: HTMLElement): boolean => {
    let changed = false;
    if (syncClass(existingRole, createdRole)) {
        changed = true;
    }
    if (syncAttributes({ target: existingRole, source: createdRole })) {
        changed = true;
    }
    const existingChildren = resolveAssistantHeaderRoleChildren(existingRole);
    const createdChildren = resolveAssistantHeaderRoleChildren(createdRole);
    const existingNav = existingChildren.comparisonNav;
    const createdNav = createdChildren.comparisonNav;
    if ((existingNav === null) !== (createdNav === null)) {
        return patchAssistantRoleNodeStructure(existingRole, createdRole) || changed;
    }
    if (existingNav && createdNav) {
        const navChanged = patchAssistantComparisonNav(existingNav, createdNav);
        if (navChanged === null) {
            return patchAssistantRoleNodeStructure(existingRole, createdRole) || changed;
        }
        return navChanged || changed;
    }
    const existingActivity = existingChildren.assistantActivity;
    const createdActivity = createdChildren.assistantActivity;
    if (!existingActivity || !createdActivity) {
        return patchAssistantRoleNodeStructure(existingRole, createdRole) || changed;
    }
    if (patchAssistantHeaderActivity(existingActivity, createdActivity)) {
        changed = true;
    }
    return changed;
};

const patchAssistantMessageHeader = (existingHeader: HTMLElement, createdHeader: HTMLElement): boolean => {
    let changed = false;
    if (syncClass(existingHeader, createdHeader)) {
        changed = true;
    }
    if (syncAttributes({ target: existingHeader, source: createdHeader })) {
        changed = true;
    }
    const existingRole = resolveMessageRoleChild(existingHeader);
    const createdRole = resolveMessageRoleChild(createdHeader);
    if (!existingRole && !createdRole) {
        return changed;
    }
    if (!existingRole || !createdRole) {
        return patchElementChildren(existingHeader, createdHeader) || changed;
    }
    return patchAssistantMessageRole(existingRole, createdRole) || changed;
};

export { patchAssistantMessageHeader };
