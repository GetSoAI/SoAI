/* SoAI - Chat message root in-place patch transaction [frontend/assets/ts/features/chat/message/chatMessageRootPatchTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { preserveChatMessageInlineState, restoreChatMessageInlineState } from '@features/chat/message/chatMessageInlineStatePreservation.ts';
import { parseRenderedMarkupRoot } from '@features/chat/message/renderedMarkupRoot.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type ChatMessageRootPatchResult = {
    root: HTMLElement;
    changed: boolean;
    requiresPostRender: boolean;
};

type ChatMessageContentChildType = 'header' | 'text' | 'actions';
type ChatMessageRootChildType = 'avatar' | 'content';

const CHAT_MESSAGE_CONTENT_CHILD_TYPES: readonly ChatMessageContentChildType[] = ['header', 'text', 'actions'];
const CHAT_MESSAGE_ROOT_CHILD_TYPES: readonly ChatMessageRootChildType[] = ['avatar', 'content'];

const cloneHTMLElement = (source: HTMLElement): HTMLElement => {
    const cloned = source.cloneNode(true);
    if (!(cloned instanceof HTMLElement)) {
        throw new Error('Chat message root patch failed to clone an element.');
    }
    return cloned;
};

const resolveRootChildType = (element: HTMLElement): ChatMessageRootChildType | null => {
    if (element.classList.contains('message-avatar')) {
        return 'avatar';
    }
    if (element.classList.contains('message-content')) {
        return 'content';
    }
    return null;
};

const resolveContentChildType = (element: HTMLElement): ChatMessageContentChildType | null => {
    if (element.classList.contains('message-header')) {
        return 'header';
    }
    if (element.classList.contains('message-text')) {
        return 'text';
    }
    if (element.classList.contains('message-actions')) {
        return 'actions';
    }
    return null;
};

const mapTypedChildren = <T extends string>(parent: HTMLElement, resolveType: (element: HTMLElement) => T | null): Map<T, HTMLElement> => {
    const children = new Map<T, HTMLElement>();
    for (const child of Array.from(parent.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        const childType = resolveType(child);
        if (childType === null) {
            throw new Error('Chat message root patch requires canonical message children.');
        }
        if (children.has(childType)) {
            throw new Error('Chat message root patch found duplicate canonical message children.');
        }
        children.set(childType, child);
    }
    return children;
};

const patchLeafElement = (target: HTMLElement, source: HTMLElement): boolean => {
    let changed = syncElementShell({ target, source });
    if (replaceChildrenIfChanged(target, source)) {
        changed = true;
    }
    return changed;
};

const removeAbsentTypedChildren = <T extends string>(existingChildren: ReadonlyMap<T, HTMLElement>, createdChildren: ReadonlyMap<T, HTMLElement>, childTypes: readonly T[]): boolean => {
    let changed = false;
    for (const childType of childTypes) {
        if (!createdChildren.has(childType)) {
            const existing = existingChildren.get(childType) ?? null;
            if (existing !== null) {
                existing.remove();
                changed = true;
            }
        }
    }
    return changed;
};

const patchTypedChildren = <T extends string>(inputArguments: { target: HTMLElement; source: HTMLElement; childTypes: readonly T[]; resolveType: (element: HTMLElement) => T | null; patchChild: (target: HTMLElement, source: HTMLElement) => boolean }): boolean => {
    const existingChildren = mapTypedChildren(inputArguments.target, inputArguments.resolveType);
    const createdChildren = mapTypedChildren(inputArguments.source, inputArguments.resolveType);
    let changed = removeAbsentTypedChildren(existingChildren, createdChildren, inputArguments.childTypes);
    let anchor: ChildNode | null = inputArguments.target.firstChild;
    for (const sourceChild of Array.from(inputArguments.source.children)) {
        if (!(sourceChild instanceof HTMLElement)) {
            continue;
        }
        const childType = inputArguments.resolveType(sourceChild);
        if (childType === null) {
            continue;
        }
        const existingChild = existingChildren.get(childType) ?? null;
        if (existingChild === null) {
            const inserted = cloneHTMLElement(sourceChild);
            inputArguments.target.insertBefore(inserted, anchor);
            anchor = inserted.nextSibling;
            changed = true;
            continue;
        }
        if (anchor !== existingChild) {
            inputArguments.target.insertBefore(existingChild, anchor);
            changed = true;
        } else {
            anchor = existingChild.nextSibling;
        }
        if (inputArguments.patchChild(existingChild, sourceChild)) {
            changed = true;
        }
    }
    return changed;
};

const patchMessageContent = (target: HTMLElement, source: HTMLElement): boolean => {
    let changed = syncElementShell({ target, source });
    if (
        patchTypedChildren({
            target,
            source,
            childTypes: CHAT_MESSAGE_CONTENT_CHILD_TYPES,
            resolveType: resolveContentChildType,
            patchChild: patchLeafElement
        })
    ) {
        changed = true;
    }
    return changed;
};

const applyChatMessageRootPatchTransaction = (inputArguments: { existingRoot: HTMLElement; nextMarkup: TrustedHtml; messageDomId: string }): ChatMessageRootPatchResult => {
    const preserved = preserveChatMessageInlineState(inputArguments.existingRoot);
    const replacement = parseRenderedMarkupRoot({
        documentRef: inputArguments.existingRoot.ownerDocument,
        nextMarkup: inputArguments.nextMarkup,
        context: inputArguments.existingRoot.ownerDocument,
        failureMessage: 'Chat message root patch failed to parse rendered markup.'
    });
    if (!replacement.classList.contains('chat-message')) {
        throw new Error('Chat message root patch requires a canonical chat message root.');
    }
    if (replacement.getAttribute('data-id') !== inputArguments.messageDomId) {
        replacement.setAttribute('data-id', inputArguments.messageDomId);
    }
    let changed = syncElementShell({ target: inputArguments.existingRoot, source: replacement });
    if (
        patchTypedChildren({
            target: inputArguments.existingRoot,
            source: replacement,
            childTypes: CHAT_MESSAGE_ROOT_CHILD_TYPES,
            resolveType: resolveRootChildType,
            patchChild: (target, source) => (resolveRootChildType(target) === 'content' ? patchMessageContent(target, source) : patchLeafElement(target, source))
        })
    ) {
        changed = true;
    }
    restoreChatMessageInlineState(inputArguments.existingRoot, preserved);
    return {
        root: inputArguments.existingRoot,
        changed,
        requiresPostRender: changed
    };
};

export { applyChatMessageRootPatchTransaction };
