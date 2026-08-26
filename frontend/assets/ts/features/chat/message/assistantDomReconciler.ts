/* SoAI - Assistant DOM reconciliation policy for chat rendering [frontend/assets/ts/features/chat/message/assistantDomReconciler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { cloneInlineMediaCardsIntoPreservedPositions, restoreInlineMediaCardsFromPreservation } from '@features/chat/message/assistantInlineMediaCardPreservation.ts';
import { collectAssistantDomState, discardInlineMediaCardsFromAssistantDomState, restoreAssistantDomState, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { readPreviewImageOpenSource, readPreviewImageSource } from '@features/chat/message/multimediaPreviewImageIdentity.ts';

type AssistantDomReconcileMode = 'streamingRichText' | 'terminalFinalize' | 'messageBodyPatch';
type ConnectedReplacementCommit = {
    target: HTMLElement;
    replacementRoot: HTMLElement;
    originalChildren: ReadonlyArray<ChildNode>;
    retainedOriginalChildren: ReadonlySet<ChildNode>;
};

const resolveAssistantDomState = (target: HTMLElement, state: AssistantDomStatePreservation | null | undefined): AssistantDomStatePreservation => {
    return state ?? collectAssistantDomState(target);
};

const moveSourceChildrenIntoConnectedReplacement = (target: HTMLElement, source: HTMLElement): { originalChildren: ChildNode[]; replacementRoot: HTMLElement } => {
    if (target === source) {
        throw new Error('Assistant DOM reconciliation requires separate target and source elements.');
    }
    const originalChildren = Array.from(target.childNodes);
    const replacementRoot = target.ownerDocument.createElement('div');
    target.appendChild(replacementRoot);
    replacementRoot.append(...Array.from(source.childNodes));
    return { originalChildren, replacementRoot };
};

const commitConnectedReplacement = (inputArguments: ConnectedReplacementCommit): void => {
    for (const node of Array.from(inputArguments.replacementRoot.childNodes)) {
        inputArguments.target.insertBefore(node, inputArguments.replacementRoot);
    }
    inputArguments.replacementRoot.remove();
    for (const node of inputArguments.originalChildren) {
        if (inputArguments.retainedOriginalChildren.has(node)) {
            continue;
        }
        if (node.parentNode === inputArguments.target) {
            node.remove();
        }
    }
};

const restoreInlineMediaCards = (container: HTMLElement, state: AssistantDomStatePreservation): void => {
    restoreInlineMediaCardsFromPreservation(container, state.inlineMediaCards);
};

const copyImageDataset = (target: HTMLImageElement, source: HTMLImageElement): void => {
    for (const attribute of Array.from(source.attributes)) {
        if (attribute.name.startsWith('data-')) {
            target.setAttribute(attribute.name, attribute.value);
        }
    }
};

const preserveExistingRemoteImageProxyAttributes = (target: HTMLElement, sourceRoot: HTMLElement): void => {
    const existingImages = dom.resolveAll('img', target).filter((element): element is HTMLImageElement => element instanceof HTMLImageElement);
    const sourceImages = dom.resolveAll('img', sourceRoot).filter((element): element is HTMLImageElement => element instanceof HTMLImageElement);
    const consumed = new Set<HTMLImageElement>();

    for (const sourceImage of sourceImages) {
        const sourceOriginal = readPreviewImageOpenSource(sourceImage);
        if (!sourceOriginal) {
            continue;
        }
        const existingImage = existingImages.find((candidate) => !consumed.has(candidate) && readPreviewImageOpenSource(candidate) === sourceOriginal) ?? null;
        if (existingImage === null) {
            continue;
        }
        consumed.add(existingImage);
        const existingSource = readPreviewImageSource(existingImage);
        if (existingSource && existingSource !== readPreviewImageSource(sourceImage)) {
            sourceImage.setAttribute('src', existingSource);
        }
        copyImageDataset(sourceImage, existingImage);
    }
};

const reconcileConnectedReplacement = (target: HTMLElement, source: HTMLElement, state: AssistantDomStatePreservation): void => {
    const replacement = moveSourceChildrenIntoConnectedReplacement(target, source);
    restoreInlineMediaCards(replacement.replacementRoot, state);
    const retainedOriginalChildren = new Set(replacement.originalChildren.filter((originalChild) => originalChild.parentNode !== target));
    for (const originalChild of replacement.originalChildren) {
        if (originalChild instanceof HTMLElement && originalChild.parentNode === target) {
            discardInlineMediaCardsFromAssistantDomState(originalChild, state);
        }
    }
    commitConnectedReplacement({
        target,
        replacementRoot: replacement.replacementRoot,
        originalChildren: replacement.originalChildren,
        retainedOriginalChildren
    });
    restoreAssistantDomState(target, state);
};

const reconcileStreamingRichText = (target: HTMLElement, source: HTMLElement, state: AssistantDomStatePreservation): void => {
    if (target === source) {
        throw new Error('Assistant streaming DOM reconciliation requires separate target and source elements.');
    }
    const sourceRoot = target.ownerDocument.createElement('div');
    sourceRoot.append(...Array.from(source.childNodes));
    cloneInlineMediaCardsIntoPreservedPositions(sourceRoot, state.inlineMediaCards);
    preserveExistingRemoteImageProxyAttributes(target, sourceRoot);
    reconcileChildNodes(target, Array.from(sourceRoot.childNodes));
    restoreAssistantDomState(target, state);
};

const reconcileAssistantDom = (inputArguments: { target: HTMLElement; source: HTMLElement; mode: AssistantDomReconcileMode; state?: AssistantDomStatePreservation | null }): void => {
    const state = resolveAssistantDomState(inputArguments.target, inputArguments.state);
    if (inputArguments.mode === 'streamingRichText') {
        reconcileStreamingRichText(inputArguments.target, inputArguments.source, state);
        return;
    }
    reconcileConnectedReplacement(inputArguments.target, inputArguments.source, state);
};

const insertOrReplaceAssistantDomChild = (inputArguments: { parent: Node; element: HTMLElement; anchor: ChildNode | null; state: AssistantDomStatePreservation; target?: HTMLElement | null }): HTMLElement => {
    const target = inputArguments.target ?? null;
    if (target !== null) {
        preserveExistingRemoteImageProxyAttributes(target, inputArguments.element);
    }
    inputArguments.parent.insertBefore(inputArguments.element, inputArguments.anchor);
    restoreInlineMediaCards(inputArguments.element, inputArguments.state);
    restoreAssistantDomState(inputArguments.element, inputArguments.state);
    if (target !== null && target.parentNode === inputArguments.parent) {
        discardInlineMediaCardsFromAssistantDomState(target, inputArguments.state);
        target.remove();
    }
    return inputArguments.element;
};

const discardAssistantDomNode = (root: HTMLElement, state: AssistantDomStatePreservation): void => {
    discardInlineMediaCardsFromAssistantDomState(root, state);
};

export { discardAssistantDomNode, insertOrReplaceAssistantDomChild, reconcileAssistantDom };
