/* SoAI - Chat feature assistant timeline segment patching [frontend/assets/ts/features/chat/message/assistantTimelineSegmentPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { haveEqualChildNodes, syncAttributes, syncClass } from '@core/dom/patching.ts';
import { patchAssistantBodyChildrenInPlace } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { reconcileAssistantDom } from '@features/chat/message/assistantDomReconciler.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { collectCanonicalStreamingTextChildNodes } from '@features/chat/message/assistantStreamingDomState.ts';
import { formatAssistantBodySegmentSignature } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { patchInlineActivityHeaderChildrenInPlace } from '@features/chat/message/messageview/inlineActivityHeaderChildrenPatching.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { patchToolDetailsMarkup } from '@features/chat/message/assistantToolDetailsPatching.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { resolveDirectStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';
import { patchRichTextContent } from '@features/chat/stream/streamRichTextPatching.ts';
import { patchStreamingPlainTextContinuation } from '@features/chat/stream/streamRichTextTailContinuation.ts';
import { wrapStreamingTextFadeTailHtml } from '@features/chat/stream/streamingTextFadeTail.ts';
import { normalizeStreamingRevealTree } from '@features/chat/stream/streamingTextFadeWrap.ts';

const PRESERVED_INLINE_ACTIVITY_ATTRIBUTE_NAMES = new Set<string>(['data-collapsed', INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_LOADING_ATTRIBUTE]);

const resolveDirectInlineActionUpdateText = (root: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-action-update-text')) {
            return child;
        }
    }
    return null;
};

const resolveDirectInlineActivityHeader = (root: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-activity-header')) {
            return child;
        }
    }
    return null;
};

const hasDirectInlineActivityDetails = (root: HTMLElement): boolean => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-activity-details')) {
            return true;
        }
    }
    return false;
};

const isStreamingTextRoot = (element: HTMLElement): boolean => element.getAttribute('data-stream-text') === 'true';

const isTimelineTextRoot = (element: HTMLElement): boolean => element.classList.contains('message-stream-text-block') || isStreamingTextRoot(element);

type StreamingTextSettlementProof = {
    immutableNodes: readonly HTMLElement[];
    settled: HTMLElement;
    tail: HTMLElement;
};

const flattenStreamingTextRoot = (element: HTMLElement): boolean => {
    if (!isStreamingTextRoot(element)) {
        return false;
    }
    element.replaceChildren(...collectCanonicalStreamingTextChildNodes(element));
    return true;
};

const createRichTextSourceRoot = (target: HTMLElement, html: string): HTMLElement => {
    const source = target.ownerDocument.createElement('div');
    const fragment = createHtmlFragment({ documentRef: target.ownerDocument, html, context: target });
    source.append(...Array.from(fragment.childNodes));
    return source;
};

const cloneElement = (element: HTMLElement): HTMLElement => {
    const cloned = element.cloneNode(true);
    if (!(cloned instanceof HTMLElement)) {
        throw new Error('Streaming text settlement failed to clone an element');
    }
    return cloned;
};

const createChildNodeSourceRoot = (target: HTMLElement, nodes: readonly ChildNode[]): HTMLElement => {
    const source = target.ownerDocument.createElement('div');
    source.append(...nodes.map((node) => node.cloneNode(true)));
    return source;
};

const normalizedRevealChildrenEqual = (existing: HTMLElement, source: HTMLElement): boolean => {
    const normalizedExisting = cloneElement(existing);
    normalizeStreamingRevealTree(normalizedExisting);
    normalizedExisting.normalize();
    return haveEqualChildNodes(normalizedExisting, source);
};

const proofMatchesStreamingContainers = (proof: StreamingTextSettlementProof, settled: HTMLElement, tail: HTMLElement): boolean => {
    if (proof.settled !== settled || proof.tail !== tail || settled.children.length !== proof.immutableNodes.length) {
        return false;
    }
    return proof.immutableNodes.every((node, index) => settled.children[index] === node);
};

const resolveDirectStreamingTextContainers = (root: HTMLElement): { settled: HTMLElement; tail: HTMLElement } | null => {
    let settled: HTMLElement | null = null;
    let tail: HTMLElement | null = null;
    for (const child of Array.from(root.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (child.getAttribute('data-stream-text-settled') === 'true') {
            settled = child;
        } else if (child.getAttribute('data-stream-text-tail') === 'true') {
            tail = child;
        }
    }
    return settled !== null && tail !== null && settled !== tail ? { settled, tail } : null;
};

const patchCompletedStreamingTextRoot = (inputArguments: { existing: HTMLElement; created: HTMLElement; assistantDomState?: AssistantDomStatePreservation | null; proof: StreamingTextSettlementProof | null }): boolean => {
    const containers = resolveDirectStreamingTextContainers(inputArguments.existing);
    if (containers === null) {
        return false;
    }
    const { settled, tail } = containers;
    const proofMatches = inputArguments.proof !== null && proofMatchesStreamingContainers(inputArguments.proof, settled, tail);
    const immutableNodeCount = settled.childNodes.length;
    const createdChildren = Array.from(inputArguments.created.childNodes);
    if (createdChildren.length < immutableNodeCount) {
        return false;
    }
    const createdTail = createChildNodeSourceRoot(inputArguments.created, createdChildren.slice(immutableNodeCount));
    if (!proofMatches) {
        const createdImmutable = createChildNodeSourceRoot(inputArguments.created, createdChildren.slice(0, immutableNodeCount));
        if (!normalizedRevealChildrenEqual(settled, createdImmutable)) {
            return false;
        }
    }
    if (!normalizedRevealChildrenEqual(tail, createdTail)) {
        reconcileAssistantDom({ target: tail, source: createdTail, mode: 'streamingRichText', state: inputArguments.assistantDomState ?? null });
    }
    normalizeStreamingRevealTree(settled);
    normalizeStreamingRevealTree(tail);
    inputArguments.existing.replaceChildren(...Array.from(settled.childNodes), ...Array.from(tail.childNodes));
    return true;
};

const patchInlineActionUpdateTextAppend = (existingText: HTMLElement, createdText: HTMLElement): boolean => {
    const existingValue = existingText.textContent ?? '';
    const createdValue = createdText.textContent ?? '';
    if (!createdValue.startsWith(existingValue) || createdValue.length === existingValue.length) {
        return false;
    }
    const appendText = createdValue.slice(existingValue.length);
    const proof = cloneElement(existingText);
    const proofResult = patchStreamingPlainTextContinuation({ tail: proof, appendText });
    if (!proofResult.patched) {
        return false;
    }
    normalizeStreamingRevealTree(proof);
    proof.normalize();
    if (!haveEqualChildNodes(proof, createdText)) {
        return false;
    }
    const result = patchStreamingPlainTextContinuation({ tail: existingText, appendText });
    if (!result.patched) {
        throw new Error('Thinking preface continuation changed after validation');
    }
    return result.updated;
};

const patchInlineActionUpdateMarkup = (existing: HTMLElement, created: HTMLElement, applyStreamingReveal: boolean): boolean => {
    const existingText = resolveDirectInlineActionUpdateText(existing);
    const createdText = resolveDirectInlineActionUpdateText(created);
    if (!existingText || !createdText) {
        return false;
    }

    let changed = false;
    if (syncAttributes({ target: existing, source: created })) {
        changed = true;
    }

    const existingTextHtml = existingText.innerHTML;
    const createdTextHtml = createdText.innerHTML;
    const appendedInPlace = applyStreamingReveal && patchInlineActionUpdateTextAppend(existingText, createdText);
    const nextTextHtml = applyStreamingReveal && !appendedInPlace ? wrapStreamingTextFadeTailHtml(createdTextHtml, existingText) : createdTextHtml;
    if (!appendedInPlace && existingTextHtml !== nextTextHtml) {
        if (applyStreamingReveal) {
            patchRichTextContent(existingText, createdTextHtml);
        } else {
            reconcileAssistantDom({ target: existingText, source: createRichTextSourceRoot(existingText, createdTextHtml), mode: 'streamingRichText' });
        }
        changed = true;
    } else if (appendedInPlace) {
        changed = true;
    }

    if (syncClass(existing, created)) {
        changed = true;
    }
    return changed;
};

const patchCollapsedLoadingContentMarkup = (inputArguments: { preserveActiveStreamingText?: boolean; existing: HTMLElement; created: HTMLElement; assistantDomState?: AssistantDomStatePreservation | null }): { patched: boolean; detailsChanged: boolean; retainedSignature?: string } => {
    let changed = false;
    if (syncClass(inputArguments.existing, inputArguments.created)) {
        changed = true;
    }
    if (syncAttributes({ target: inputArguments.existing, source: inputArguments.created })) {
        changed = true;
    }
    const existingStreamSegments = resolveDirectStreamSegments(inputArguments.existing);
    const patchContainer = existingStreamSegments ?? inputArguments.existing;
    const contentChanged = patchAssistantBodyChildrenInPlace({
        container: patchContainer,
        nextContainer: inputArguments.created,
        assistantDomState: inputArguments.assistantDomState ?? null,
        disableInsertAnimation: true,
        patchExistingChild: (patchArguments) => patchStreamingTimelineSegmentInPlace({ ...patchArguments, preserveActiveStreamingText: inputArguments.preserveActiveStreamingText === true })
    });
    if (contentChanged === null) {
        return { patched: false, detailsChanged: false };
    }
    return {
        patched: true,
        detailsChanged: changed || contentChanged,
        ...(inputArguments.preserveActiveStreamingText === true ? { retainedSignature: formatAssistantBodySegmentSignature(inputArguments.existing.innerHTML) } : {})
    };
};

export const patchStreamingTimelineSegmentInPlace = (inputArguments: { preserveActiveStreamingText?: boolean; existing: HTMLElement; created: HTMLElement; assistantDomState?: AssistantDomStatePreservation | null; applyStreamingReveal?: boolean; streamingTextSettlementProof?: StreamingTextSettlementProof | null }): { patched: boolean; detailsChanged: boolean; retainedSignature?: string } => {
    const { existing, created } = inputArguments;
    const applyStreamingReveal = inputArguments.applyStreamingReveal === true;
    if (inputArguments.preserveActiveStreamingText === true && isStreamingTextRoot(existing) && isTimelineTextRoot(created)) {
        return { patched: true, detailsChanged: false, retainedSignature: formatAssistantBodySegmentSignature(existing.innerHTML) };
    }
    if (!existing.classList.contains('inline-activity') || !created.classList.contains('inline-activity')) {
        if (existing.classList.contains('inline-action-update') && created.classList.contains('inline-action-update')) {
            const detailsChanged = patchInlineActionUpdateMarkup(existing, created, applyStreamingReveal);
            return { patched: true, detailsChanged };
        }
        if (existing.tagName !== created.tagName) {
            return { patched: false, detailsChanged: false };
        }
        if (existing.matches(COLLAPSED_LOADING_CONTENT_SELECTOR) && created.matches(COLLAPSED_LOADING_CONTENT_SELECTOR)) {
            return patchCollapsedLoadingContentMarkup({ existing, created, preserveActiveStreamingText: inputArguments.preserveActiveStreamingText === true, assistantDomState: inputArguments.assistantDomState ?? null });
        }
        let changed = false;
        let completedStreamingTextInPlace = false;
        if (isTimelineTextRoot(existing) && isTimelineTextRoot(created) && isStreamingTextRoot(existing) && !isStreamingTextRoot(created)) {
            const completedInPlace = patchCompletedStreamingTextRoot({ existing, created, assistantDomState: inputArguments.assistantDomState ?? null, proof: inputArguments.streamingTextSettlementProof ?? null });
            if (completedInPlace) {
                changed = true;
                completedStreamingTextInPlace = true;
            } else if (flattenStreamingTextRoot(existing)) {
                changed = true;
            }
        }
        if (syncClass(existing, created)) {
            changed = true;
        }
        if (syncAttributes({ target: existing, source: created })) {
            changed = true;
        }
        if (!completedStreamingTextInPlace && !haveEqualChildNodes(existing, created)) {
            reconcileAssistantDom({ target: existing, source: created, mode: isTimelineTextRoot(existing) && isTimelineTextRoot(created) ? 'streamingRichText' : 'messageBodyPatch', state: inputArguments.assistantDomState ?? null });
            changed = true;
        }
        return { patched: true, detailsChanged: changed };
    }
    const preservedCollapsed = existing.getAttribute('data-collapsed');
    const wasCollapsing = existing.getAttribute('data-collapsing') === 'true';
    let detailsChanged = false;
    if (syncClass(existing, created)) {
        detailsChanged = true;
    }
    if (syncAttributes({ target: existing, source: created, preservedAttributeNames: PRESERVED_INLINE_ACTIVITY_ATTRIBUTE_NAMES })) {
        detailsChanged = true;
    }

    const existingHeader = resolveDirectInlineActivityHeader(existing);
    const createdHeader = resolveDirectInlineActivityHeader(created);
    if (!existingHeader || !createdHeader) {
        return { patched: false, detailsChanged: false };
    }
    if (patchInlineActivityHeaderChildrenInPlace(existingHeader, createdHeader)) {
        detailsChanged = true;
    }

    if (patchToolDetailsMarkup({ existing, created, patchActivity: patchStreamingTimelineSegmentInPlace, assistantDomState: inputArguments.assistantDomState ?? null, preserveOpenDetails: !wasCollapsing, applyStreamingReveal })) {
        detailsChanged = true;
    }
    if (!wasCollapsing && preservedCollapsed !== null && hasDirectInlineActivityDetails(existing)) {
        existing.setAttribute('data-collapsed', preservedCollapsed);
    }
    return { patched: true, detailsChanged };
};

export type { StreamingTextSettlementProof };
