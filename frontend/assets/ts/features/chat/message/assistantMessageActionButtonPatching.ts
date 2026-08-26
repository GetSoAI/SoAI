/* SoAI - Assistant message action button DOM patching [frontend/assets/ts/features/chat/message/assistantMessageActionButtonPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasDataActionElement } from '@core/dom/dataAction.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { applyChatMessageEnterAnimation, type ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';

const MESSAGE_ACTION_BUTTONS_LEFT_CLASS = 'message-action-buttons-left';
const MESSAGE_ACTION_BUTTONS_RIGHT_CLASS = 'message-action-buttons-right';
const TIMESTAMP_ACTION_KEY = 'copy-timestamp';

type ActionButtonGroupChildren = {
    left: HTMLElement | null;
    right: HTMLElement | null;
};

type TimestampContentPatchResult = {
    supported: boolean;
    changed: boolean;
};

type ActionButtonGroupIgnorePredicate = (element: HTMLElement) => boolean;

const resolveActionButtonGroupChildren = (group: HTMLElement): ActionButtonGroupChildren => {
    const resolved: ActionButtonGroupChildren = {
        left: null,
        right: null
    };
    for (const child of Array.from(group.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (resolved.left === null && child.classList.contains(MESSAGE_ACTION_BUTTONS_LEFT_CLASS)) {
            resolved.left = child;
            continue;
        }
        if (resolved.right === null && child.classList.contains(MESSAGE_ACTION_BUTTONS_RIGHT_CLASS)) {
            resolved.right = child;
        }
    }
    return resolved;
};

const resolveActionButtonKey = (button: HTMLElement): string | null => {
    if (!hasDataActionElement(button)) {
        return null;
    }
    const action = button.dataset.action;
    if (!action || !action.trim()) {
        return null;
    }
    return action.trim();
};

const resolveElement = (root: HTMLElement, selector: string): HTMLElement | null => {
    const element = dom.resolve(selector, root);
    return element instanceof HTMLElement ? element : null;
};

const syncElementText = (existingRoot: HTMLElement, createdRoot: HTMLElement, selector: string): TimestampContentPatchResult => {
    const existing = resolveElement(existingRoot, selector);
    const created = resolveElement(createdRoot, selector);
    if (!existing || !created) {
        return { supported: existing === null && created === null, changed: false };
    }
    if (existing.textContent === created.textContent) {
        return { supported: true, changed: false };
    }
    existing.textContent = created.textContent;
    return { supported: true, changed: true };
};

const patchTimestampButtonContent = (existingButton: HTMLElement, createdButton: HTMLElement): TimestampContentPatchResult => {
    const existingContent = resolveElement(existingButton, '.message-timestamp-btn-content');
    const createdContent = resolveElement(createdButton, '.message-timestamp-btn-content');
    if (!existingContent || !createdContent) {
        if (existingContent === null && createdContent === null) {
            if (existingButton.textContent === createdButton.textContent) {
                return { supported: true, changed: false };
            }
            existingButton.textContent = createdButton.textContent;
            return { supported: true, changed: true };
        }
        return { supported: false, changed: false };
    }
    let changed = false;
    const durationText = syncElementText(existingContent, createdContent, '.message-timestamp-duration-text');
    if (!durationText.supported) {
        return { supported: false, changed: false };
    }
    if (durationText.changed) {
        changed = true;
    }
    const timestampText = syncElementText(existingContent, createdContent, '.message-timestamp-text');
    if (!timestampText.supported) {
        return { supported: false, changed: false };
    }
    if (timestampText.changed) {
        changed = true;
    }
    return { supported: true, changed };
};

const patchActionButton = (existingButton: HTMLElement, createdButton: HTMLElement, key: string): boolean => {
    let changed = syncElementShell({ target: existingButton, source: createdButton });
    if (key === TIMESTAMP_ACTION_KEY) {
        const contentPatch = patchTimestampButtonContent(existingButton, createdButton);
        if (contentPatch.supported) {
            return changed || contentPatch.changed;
        }
    }
    if (replaceChildrenIfChanged(existingButton, createdButton)) {
        changed = true;
    }
    return changed;
};

const resolveFirstPatchableChild = (group: HTMLElement, ignoreElement: ActionButtonGroupIgnorePredicate | null): ChildNode | null => {
    if (ignoreElement === null) {
        return group.firstChild;
    }
    for (const child of Array.from(group.childNodes)) {
        if (child instanceof HTMLElement && !ignoreElement(child)) {
            return child;
        }
    }
    return null;
};

const patchActionButtonGroup = (existingGroup: HTMLElement, createdGroup: HTMLElement, options: ChatMessageInsertAnimationOptions, ignoreElement: ActionButtonGroupIgnorePredicate | null): boolean => {
    let changed = syncElementShell({ target: existingGroup, source: createdGroup });
    const existingButtons = new Map<string, HTMLElement>();
    for (const child of Array.from(existingGroup.children)) {
        if (!(child instanceof HTMLElement)) {
            throw new Error('Assistant message action patch requires canonical existing action nodes.');
        }
        if (ignoreElement !== null && ignoreElement(child)) {
            continue;
        }
        const key = resolveActionButtonKey(child);
        if (!key || existingButtons.has(key)) {
            throw new Error('Assistant message action patch requires unique existing action keys.');
        }
        existingButtons.set(key, child);
    }
    let anchor: ChildNode | null = resolveFirstPatchableChild(existingGroup, ignoreElement);
    const seenKeys = new Set<string>();
    for (const child of Array.from(createdGroup.children)) {
        if (!(child instanceof HTMLElement)) {
            throw new Error('Assistant message action patch requires canonical created action nodes.');
        }
        if (ignoreElement !== null && ignoreElement(child)) {
            continue;
        }
        const key = resolveActionButtonKey(child);
        if (!key || seenKeys.has(key)) {
            throw new Error('Assistant message action patch requires unique created action keys.');
        }
        seenKeys.add(key);
        const existingButton = existingButtons.get(key) ?? null;
        if (!existingButton) {
            const inserted = child.cloneNode(true);
            if (!(inserted instanceof HTMLElement)) {
                throw new Error('Assistant message action patch failed to clone created action.');
            }
            applyChatMessageEnterAnimation(inserted, options);
            existingGroup.insertBefore(inserted, anchor);
            anchor = inserted.nextSibling;
            changed = true;
            continue;
        }
        if (patchActionButton(existingButton, child, key)) {
            changed = true;
        }
        if (anchor !== existingButton) {
            existingGroup.insertBefore(existingButton, anchor);
            changed = true;
        }
        anchor = existingButton.nextSibling;
        existingButtons.delete(key);
    }
    for (const leftover of existingButtons.values()) {
        leftover.remove();
        changed = true;
    }
    return changed;
};

const patchMessageActionButtonGroup = (existingGroup: HTMLElement, createdGroup: HTMLElement, options: ChatMessageInsertAnimationOptions = {}, ignoreElement: ActionButtonGroupIgnorePredicate | null = null): boolean => {
    return patchActionButtonGroup(existingGroup, createdGroup, options, ignoreElement);
};

const patchMessageActionButtons = (existingButtons: HTMLElement, createdButtons: HTMLElement, options: ChatMessageInsertAnimationOptions = {}): boolean => {
    let changed = syncElementShell({ target: existingButtons, source: createdButtons });
    const existingChildren = resolveActionButtonGroupChildren(existingButtons);
    const createdChildren = resolveActionButtonGroupChildren(createdButtons);
    const existingLeft = existingChildren.left;
    const createdLeft = createdChildren.left;
    const existingRight = existingChildren.right;
    const createdRight = createdChildren.right;
    if (!existingLeft || !createdLeft || !existingRight || !createdRight) {
        throw new Error('Assistant message action patch requires canonical action button groups.');
    }
    if (patchActionButtonGroup(existingLeft, createdLeft, options, null)) {
        changed = true;
    }
    if (patchActionButtonGroup(existingRight, createdRight, options, null)) {
        changed = true;
    }
    return changed;
};

export { patchMessageActionButtonGroup, patchMessageActionButtons };
