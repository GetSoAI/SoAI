/* SoAI - Assistant message keyed child retention registry [frontend/assets/ts/features/chat/message/assistantKeyedChildRetention.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamChildItem } from '@features/chat/message/assistantKeyedPatchContracts.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, formatAssistantBodySegmentSignature } from '@features/chat/message/assistantMessageMarkupParts.ts';

type AssistantKeyedChildRegistry = {
    existingByKey: Map<string, HTMLElement>;
    retainedChildren: Set<HTMLElement>;
};

const resolveDesiredSignatureAttribute = (item: StreamChildItem): string | null => {
    const kind = item.signatureKind ?? 'rawModel';
    if (kind === 'attribute') {
        return item.signature;
    }
    return formatAssistantBodySegmentSignature(item.signature);
};

const stampAssistantBodySegmentSignature = (element: HTMLElement, desiredSignature: string | null): void => {
    if (desiredSignature === null) {
        return;
    }
    if (element.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME) !== desiredSignature) {
        element.setAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, desiredSignature);
    }
};

const elementSignatureMatches = (element: HTMLElement, desiredSignature: string | null): boolean => {
    return desiredSignature !== null && element.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME) === desiredSignature;
};

const orderedChildrenMatchKeys = (children: readonly HTMLElement[], orderedKeys: readonly string[]): boolean => {
    if (children.length !== orderedKeys.length) {
        return false;
    }
    for (let index = 0; index < orderedKeys.length; index += 1) {
        if (children[index]?.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME) !== orderedKeys[index]) {
            return false;
        }
    }
    return true;
};

const canSkipAssistantKeyedPatch = (inputArguments: { container: HTMLElement; orderedKeys: readonly string[]; desiredSignatureByKey: ReadonlyMap<string, string | null> }): boolean => {
    const children = Array.from(inputArguments.container.children).filter((node): node is HTMLElement => node instanceof HTMLElement);
    if (!orderedChildrenMatchKeys(children, inputArguments.orderedKeys)) {
        return false;
    }
    for (let index = 0; index < inputArguments.orderedKeys.length; index += 1) {
        const child = children[index];
        const desiredSignature = inputArguments.desiredSignatureByKey.get(inputArguments.orderedKeys[index] ?? '') ?? null;
        if (!child || !elementSignatureMatches(child, desiredSignature)) {
            return false;
        }
    }
    return true;
};

const createAssistantKeyedChildRegistry = (container: HTMLElement, keyAttributeName: string): AssistantKeyedChildRegistry => {
    const existingByKey = new Map<string, HTMLElement>();
    for (const child of Array.from(container.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        const key = child.getAttribute(keyAttributeName);
        if (key && !existingByKey.has(key)) {
            existingByKey.set(key, child);
        }
    }
    return { existingByKey, retainedChildren: new Set<HTMLElement>() };
};

const collectUnretainedDirectElementChildren = (container: HTMLElement, retainedChildren: ReadonlySet<HTMLElement>): HTMLElement[] => {
    const unretained: HTMLElement[] = [];
    for (const child of Array.from(container.children)) {
        if (child instanceof HTMLElement && !retainedChildren.has(child)) {
            unretained.push(child);
        }
    }
    return unretained;
};

export { canSkipAssistantKeyedPatch, collectUnretainedDirectElementChildren, createAssistantKeyedChildRegistry, elementSignatureMatches, resolveDesiredSignatureAttribute, stampAssistantBodySegmentSignature };
