/* SoAI - Assistant message DOM part resolution and keyed segment extraction [frontend/assets/ts/features/chat/message/assistantMessageMarkupParts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isWhitespaceTextNode } from '@core/dom/domEnvironment.ts';
import { computeHash } from '@core/primitives/hash.ts';

type AssistantBodySignatureKind = 'rawModel' | 'attribute';

type KeyedAssistantBodyItem = {
    key: string;
    signature: string;
    element: HTMLElement;
    signatureKind: AssistantBodySignatureKind;
};

const ASSISTANT_BODY_KEY_ATTRIBUTE_NAME = 'data-stream-segment-key';
const ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME = 'data-stream-segment-signature';

const formatAssistantBodySegmentSignature = (raw: string): string => `${String(raw.length)}:${computeHash(raw).toString(36)}`;

const buildAssistantBodyItems = (responseRoot: HTMLElement): KeyedAssistantBodyItem[] | null => {
    const items: KeyedAssistantBodyItem[] = [];
    const keys = new Set<string>();
    for (const child of Array.from(responseRoot.childNodes)) {
        if (child instanceof HTMLElement) {
            const attributeKey = (child.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME) ?? '').trim();
            const attributeSignature = (child.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME) ?? '').trim();
            if (!attributeKey || !attributeSignature || keys.has(attributeKey)) {
                return null;
            }
            keys.add(attributeKey);
            items.push({
                key: attributeKey,
                signature: attributeSignature,
                element: child,
                signatureKind: 'attribute'
            });
            continue;
        }
        if (!isWhitespaceTextNode(child)) {
            return null;
        }
    }
    return items;
};

const collectDirectElementChildren = (root: HTMLElement): HTMLElement[] | null => {
    const children: HTMLElement[] = [];
    for (const child of Array.from(root.childNodes)) {
        if (child instanceof HTMLElement) {
            children.push(child);
            continue;
        }
        if (!isWhitespaceTextNode(child)) {
            return null;
        }
    }
    return children;
};

type AssistantMessageParts = {
    avatar: HTMLElement | null;
    content: HTMLElement;
    header: HTMLElement | null;
    text: HTMLElement;
    response: HTMLElement | null;
    actions: HTMLElement | null;
};

const resolveAssistantMessageResponseRoot = (textRoot: HTMLElement): HTMLElement | null => {
    const textChildren = collectDirectElementChildren(textRoot);
    if (!textChildren || textChildren.length !== 1) {
        return null;
    }
    const response = textChildren[0];
    if (!response || !response.classList.contains('message-response')) {
        return null;
    }
    return response;
};

const resolveAssistantMessageParts = (messageRoot: HTMLElement): AssistantMessageParts | null => {
    const rootChildren = collectDirectElementChildren(messageRoot);
    if (!rootChildren || rootChildren.length < 1 || rootChildren.length > 2) {
        return null;
    }
    const first = rootChildren[0] ?? null;
    const second = rootChildren.length === 2 ? (rootChildren[1] ?? null) : null;
    const avatar = second ? first : null;
    const content = second ? second : first;
    if (!content || !content.classList.contains('message-content')) {
        return null;
    }
    if (avatar && !avatar.classList.contains('message-avatar')) {
        return null;
    }
    const contentChildren = collectDirectElementChildren(content);
    if (!contentChildren || contentChildren.length < 1 || contentChildren.length > 3) {
        return null;
    }
    let header: HTMLElement | null = null;
    let text: HTMLElement | null = null;
    let actions: HTMLElement | null = null;
    for (const child of contentChildren) {
        if (child.classList.contains('message-header')) {
            if (header) {
                return null;
            }
            header = child;
            continue;
        }
        if (child.classList.contains('message-text')) {
            if (text) {
                return null;
            }
            text = child;
            continue;
        }
        if (child.classList.contains('message-actions')) {
            if (actions) {
                return null;
            }
            actions = child;
            continue;
        }
        return null;
    }
    if (!text) {
        return null;
    }
    const response = resolveAssistantMessageResponseRoot(text);
    return { avatar, content, header, text, response, actions };
};

export { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, buildAssistantBodyItems, formatAssistantBodySegmentSignature, resolveAssistantMessageParts, resolveAssistantMessageResponseRoot };
export type { AssistantBodySignatureKind, AssistantMessageParts, KeyedAssistantBodyItem };
