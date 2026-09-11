/* SoAI - Chat feature assistant body keyed reconciler [frontend/assets/ts/features/chat/message/assistantBodyKeyedReconciler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { discardAssistantDomNode, insertOrReplaceAssistantDomChild } from '@features/chat/message/assistantDomReconciler.ts';
import { collectAssistantDomState, resolveAssistantDomStateForPatch, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { canSkipAssistantKeyedPatch, collectUnretainedDirectElementChildren, createAssistantKeyedChildRegistry, elementSignatureMatches, resolveDesiredSignatureAttribute, stampAssistantBodySegmentSignature } from '@features/chat/message/assistantKeyedChildRetention.ts';
import { createUnchangedAssistantKeyedPatchResult, createUnsupportedAssistantKeyedPatchResult, createUpdatedAssistantKeyedPatchResult, type AssistantKeyedPatchResult, type PatchStreamingKeyedChildrenArguments } from '@features/chat/message/assistantKeyedPatchContracts.ts';
import { resolveAssistantKeyedPatchPolicy } from '@features/chat/message/assistantKeyedPatchPolicy.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, buildAssistantBodyItems } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { ActivityPatchHandler } from '@features/chat/message/assistantNestedActivityPatching.ts';
import { captureAssistantViewportStability, restoreAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { applyChatMessageEnterAnimation } from '@features/chat/message/messageMotion.ts';
import { collectMermaidContainersByKey, restoreMermaidContainersByKey } from '@features/chat/stream/streamDomCache.ts';
import { applyKeyedScrollableState, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';
import { applyStreamingTextFadeToElement, markStreamingTextContinuation } from '@features/chat/stream/streamingTextFadeWrap.ts';

const shouldApplyInsertAnimation = (node: HTMLElement, disabled: boolean): boolean => {
    if (disabled) {
        return false;
    }
    if (node.classList.contains('message-stream-text-block')) {
        return false;
    }
    if (node.classList.contains('inline-action-update')) {
        return false;
    }
    return true;
};

const shouldApplyStreamingReveal = (node: HTMLElement, inputArguments: { enabled: boolean; revealTextBlocks: boolean }): boolean => {
    if (!inputArguments.enabled) {
        return false;
    }
    if (!inputArguments.revealTextBlocks && node.classList.contains('message-stream-text-block')) {
        return false;
    }
    return true;
};

const applyStreamingRevealForInsertedChild = (node: HTMLElement, inputArguments: { enabled: boolean; revealTextBlocks: boolean }): void => {
    if (shouldApplyStreamingReveal(node, inputArguments)) {
        applyStreamingTextFadeToElement(node);
        if (node.classList.contains('inline-action-update')) {
            markStreamingTextContinuation(node);
        }
    }
};

const repositionExistingChild = (container: HTMLElement, existing: HTMLElement, anchor: ChildNode | null, currentNeedsScrollRestore: boolean): readonly [ChildNode | null, boolean] => {
    if (anchor !== existing) {
        container.insertBefore(existing, anchor);
        return [anchor, true];
    }
    return [existing.nextSibling, currentNeedsScrollRestore];
};

export const patchStreamingKeyedChildren = (inputArguments: PatchStreamingKeyedChildrenArguments): AssistantKeyedPatchResult => {
    const { container, items, cachedMarkupByKey } = inputArguments;
    const policy = resolveAssistantKeyedPatchPolicy(inputArguments.policy);
    if (buildAssistantBodyItems(container) === null) {
        return createUnsupportedAssistantKeyedPatchResult();
    }

    const nextMarkupByKey = new Map<string, string>();
    const nextSignatureByKey = new Map<string, string>();
    const desiredSignatureByKey = new Map<string, string | null>();
    const createdElementByKey = new Map<string, HTMLElement>();
    const orderedKeys: string[] = [];
    const itemKeys = new Set<string>();

    for (const item of items) {
        const hasMarkup = typeof item.markup === 'string' && item.markup.trim().length > 0;
        const hasElement = item.element instanceof HTMLElement;
        if (!item.key.trim() || !item.signature.trim() || itemKeys.has(item.key) || hasMarkup === hasElement) {
            return createUnsupportedAssistantKeyedPatchResult();
        }
        let created = item.element ?? null;
        try {
            created ??= parseSingleRootElement({ documentRef: container.ownerDocument, html: toTrustedUiHtml(item.markup ?? ''), context: container.ownerDocument });
        } catch {
            return createUnsupportedAssistantKeyedPatchResult();
        }
        if (!created) {
            return createUnsupportedAssistantKeyedPatchResult();
        }
        itemKeys.add(item.key);
        orderedKeys.push(item.key);
        nextSignatureByKey.set(item.key, item.signature);
        nextMarkupByKey.set(item.key, item.markup ?? '');
        desiredSignatureByKey.set(item.key, resolveDesiredSignatureAttribute(item));
        createdElementByKey.set(item.key, created);
    }

    if (canSkipAssistantKeyedPatch({ container, orderedKeys, desiredSignatureByKey })) {
        return createUnchangedAssistantKeyedPatchResult();
    }

    let assistantDomState = inputArguments.assistantDomState ?? null;
    let assistantDomStateResolved = assistantDomState !== null;
    const preservedScroll = readKeyedScrollableState(container);
    const preservedMermaid = collectMermaidContainersByKey(container);

    const getAssistantDomState = (): AssistantDomStatePreservation | null => {
        if (assistantDomStateResolved) {
            return assistantDomState;
        }
        assistantDomState = resolveAssistantDomStateForPatch(container, assistantDomState);
        assistantDomStateResolved = true;
        return assistantDomState;
    };

    const childRegistry = createAssistantKeyedChildRegistry(container, ASSISTANT_BODY_KEY_ATTRIBUTE_NAME);
    const existingByKey = childRegistry.existingByKey;
    const retainedChildren = childRegistry.retainedChildren;

    let needsScrollRestore = false;
    const changedElements: HTMLElement[] = [];
    const viewportStability = captureAssistantViewportStability(container);
    let anchor: ChildNode | null = container.firstChild;

    for (const key of orderedKeys) {
        const markup = nextMarkupByKey.get(key) ?? '';
        const created = createdElementByKey.get(key) ?? null;
        if (!markup && created === null) {
            continue;
        }
        const existing = existingByKey.get(key) ?? null;
        const previousMarkup = cachedMarkupByKey?.get(key) ?? null;
        const desiredSignature = desiredSignatureByKey.get(key) ?? null;

        if (existing && (policy.nonReplaceableKeys?.has(key) || previousMarkup === markup || elementSignatureMatches(existing, desiredSignature))) {
            const nextAssistantDomState = getAssistantDomState();
            if (nextAssistantDomState !== null) {
                discardAssistantDomNode(existing, nextAssistantDomState);
            }
            [anchor, needsScrollRestore] = repositionExistingChild(container, existing, anchor, needsScrollRestore);
            retainedChildren.add(existing);
            existingByKey.delete(key);
            continue;
        }

        if (!created) {
            return createUnsupportedAssistantKeyedPatchResult();
        }
        created.setAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, key);
        stampAssistantBodySegmentSignature(created, desiredSignature);

        if (existing) {
            const patchResult = inputArguments.patchExistingChild({ existing, created, assistantDomState: getAssistantDomState(), applyStreamingReveal: policy.applyStreamingReveal });
            if (patchResult.patched) {
                stampAssistantBodySegmentSignature(existing, patchResult.retainedSignature ?? desiredSignature);
                const nextAssistantDomState = getAssistantDomState();
                if (nextAssistantDomState !== null) {
                    discardAssistantDomNode(existing, nextAssistantDomState);
                }
                if (patchResult.detailsChanged) {
                    needsScrollRestore = true;
                    changedElements.push(existing);
                }
                [anchor, needsScrollRestore] = repositionExistingChild(container, existing, anchor, needsScrollRestore);
                retainedChildren.add(existing);
                existingByKey.delete(key);
                continue;
            }
            applyStreamingRevealForInsertedChild(created, { enabled: policy.applyStreamingReveal, revealTextBlocks: policy.applyStreamingRevealToTextBlocks });
            if (shouldApplyInsertAnimation(created, policy.disableInsertAnimation)) {
                applyChatMessageEnterAnimation(created);
            }
            const nextAssistantDomState = getAssistantDomState();
            if (nextAssistantDomState !== null) {
                insertOrReplaceAssistantDomChild({ parent: container, element: created, anchor, state: nextAssistantDomState, target: existing });
            } else {
                container.insertBefore(created, anchor);
            }
            if (existing.parentNode === container) {
                existing.remove();
            }
            existingByKey.delete(key);
            anchor = created.nextSibling;
            retainedChildren.add(created);
            changedElements.push(created);
            needsScrollRestore = true;
            continue;
        }

        applyStreamingRevealForInsertedChild(created, { enabled: policy.applyStreamingReveal, revealTextBlocks: policy.applyStreamingRevealToTextBlocks });
        if (shouldApplyInsertAnimation(created, policy.disableInsertAnimation)) {
            applyChatMessageEnterAnimation(created);
        }
        const nextAssistantDomState = getAssistantDomState();
        if (nextAssistantDomState !== null) {
            insertOrReplaceAssistantDomChild({ parent: container, element: created, anchor, state: nextAssistantDomState });
        } else {
            container.insertBefore(created, anchor);
        }
        anchor = created.nextSibling;
        retainedChildren.add(created);
        changedElements.push(created);
        needsScrollRestore = true;
    }

    for (const leftover of collectUnretainedDirectElementChildren(container, retainedChildren)) {
        const nextAssistantDomState = getAssistantDomState();
        if (nextAssistantDomState !== null) {
            discardAssistantDomNode(leftover, nextAssistantDomState);
        }
        leftover.remove();
        needsScrollRestore = true;
    }

    if (needsScrollRestore) {
        restoreMermaidContainersByKey(container, preservedMermaid);
        if (preservedScroll) {
            applyKeyedScrollableState(container, preservedScroll);
        }
        restoreAssistantViewportStability(viewportStability);
    }

    inputArguments.setCachedMarkupByKey?.(nextMarkupByKey);
    inputArguments.setCachedSignatureByKey?.(nextSignatureByKey);
    return createUpdatedAssistantKeyedPatchResult(changedElements);
};

export const patchAssistantBodyChildrenInPlace = (inputArguments: { container: HTMLElement; nextContainer: HTMLElement; assistantDomState?: AssistantDomStatePreservation | null; disableInsertAnimation?: boolean; patchExistingChild: ActivityPatchHandler }): boolean | null => {
    const items = buildAssistantBodyItems(inputArguments.nextContainer);
    if (items === null) {
        return null;
    }
    const assistantDomState = inputArguments.assistantDomState ?? collectAssistantDomState(inputArguments.container);
    const result = patchStreamingKeyedChildren({
        container: inputArguments.container,
        items,
        cachedMarkupByKey: null,
        cachedSignatureByKey: null,
        policy: {
            nonReplaceableKeys: null,
            disableInsertAnimation: inputArguments.disableInsertAnimation === true,
            applyStreamingReveal: false,
            applyStreamingRevealToTextBlocks: false
        },
        assistantDomState,
        patchExistingChild: inputArguments.patchExistingChild
    });
    return result.supported ? result.updated : null;
};
