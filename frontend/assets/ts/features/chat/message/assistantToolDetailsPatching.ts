/* SoAI - Chat feature assistant tool details patching [frontend/assets/ts/features/chat/message/assistantToolDetailsPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncElementShell } from '@core/dom/patching.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { insertOrReplaceAssistantDomChild } from '@features/chat/message/assistantDomReconciler.ts';
import { resolveAssistantDomStateForPatch } from '@features/chat/message/assistantDomState.ts';
import { insertClonedElementWithAssistantState, patchElementChildren, removeElementWithAssistantState } from '@features/chat/message/assistantElementPatching.ts';
import { detailsRootHasPopulatedContent, inlineActivityDetailsSignatureIsCurrent, readInlineActivityDetailsRootSignature } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { previewImagesRepresentSameMedia } from '@features/chat/message/multimediaPreviewImageIdentity.ts';
import { type ActivityPatchContext, type ActivityPatchHandler } from '@features/chat/message/assistantNestedActivityPatching.ts';
import { patchSubagentResultSection } from '@features/chat/message/assistantSubagentResultDetailsPatching.ts';
import { applyKeyedScrollableStateWithBottomDefault, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';

type DetailsSectionType = 'args' | 'diffs' | 'result' | 'error';
type ToolResultChildType = 'label' | 'media' | 'meta' | 'pre';

const INLINE_TOOL_IMAGE_PRESERVED_ATTRIBUTES = new Set(['src', 'srcset', 'sizes', 'data-inline-tool-image-lifecycle-wired', 'data-media-load-state', 'data-media-open-source-url', 'data-media-preview-url', 'data-media-download-url', 'data-media-source-type', 'data-media-source-value']);

const resolveSectionType = (section: HTMLElement): DetailsSectionType | null => {
    if (section.classList.contains('inline-tool-args')) return 'args';
    if (section.classList.contains('inline-tool-code-diffs')) return 'diffs';
    if (section.classList.contains('inline-tool-result')) return 'result';
    if (section.classList.contains('inline-tool-error')) return 'error';
    return null;
};

const resolveDirectThinkingPhase = (detailsRoot: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(detailsRoot.children)) {
        if (!(child instanceof HTMLElement)) {
            continue;
        }
        if (child.classList.contains('message-thinking-phase')) {
            return child;
        }
    }
    return null;
};

const resolveDirectChildByClass = (root: HTMLElement, className: string): HTMLElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLElement && child.classList.contains(className)) {
            return child;
        }
    }
    return null;
};

const resolveToolResultChildType = (child: HTMLElement): ToolResultChildType | null => {
    if (child.classList.contains('inline-tool-label')) return 'label';
    if (child.classList.contains('inline-tool-result-media')) return 'media';
    if (child.classList.contains('inline-tool-result-meta')) return 'meta';
    if (child.tagName.toLowerCase() === 'pre') return 'pre';
    return null;
};

const resolveDirectImage = (root: HTMLElement): HTMLImageElement | null => {
    for (const child of Array.from(root.children)) {
        if (child instanceof HTMLImageElement) {
            return child;
        }
    }
    return null;
};

const patchInlineToolResultMedia = (existingChild: HTMLElement, createdChild: HTMLElement, context: ActivityPatchContext): boolean => {
    const existingFigure = resolveDirectChildByClass(existingChild, 'inline-tool-image');
    const createdFigure = resolveDirectChildByClass(createdChild, 'inline-tool-image');
    if (existingFigure === null || createdFigure === null) {
        return patchElementChildren(existingChild, createdChild, context);
    }
    const existingImage = resolveDirectImage(existingFigure);
    const createdImage = resolveDirectImage(createdFigure);
    if (existingImage === null || createdImage === null || !previewImagesRepresentSameMedia(existingImage, createdImage)) {
        return patchElementChildren(existingChild, createdChild, context);
    }
    let changed = syncElementShell({ target: existingChild, source: createdChild });
    if (syncElementShell({ target: existingFigure, source: createdFigure })) {
        changed = true;
    }
    if (syncElementShell({ target: existingImage, source: createdImage, preservedAttributeNames: INLINE_TOOL_IMAGE_PRESERVED_ATTRIBUTES })) {
        changed = true;
    }
    return changed;
};

const patchScrollableDetailsSection = (existingChild: HTMLElement, createdChild: HTMLElement, context: ActivityPatchContext): boolean => {
    const preservedScroll = readKeyedScrollableState(existingChild);
    const changed = patchElementChildren(existingChild, createdChild, context);
    applyKeyedScrollableStateWithBottomDefault(existingChild, preservedScroll, existingChild);
    return changed;
};

const patchToolResultSection = (existingChild: HTMLElement, createdChild: HTMLElement, context: ActivityPatchContext): boolean => {
    const preservedScroll = readKeyedScrollableState(existingChild);
    let changed = syncElementShell({ target: existingChild, source: createdChild });
    if (
        patchOrderedChildren({
            existingParent: existingChild,
            createdParent: createdChild,
            resolveChildKey: resolveToolResultChildType,
            insertChild: (parent, child, anchor) => insertClonedElementWithAssistantState(parent, child, anchor, context),
            patchChild: (existingResultChild, createdResultChild, childType) => (childType === 'media' ? patchInlineToolResultMedia(existingResultChild, createdResultChild, context) : patchElementChildren(existingResultChild, createdResultChild, context)),
            removeChild: (existingResultChild) => removeElementWithAssistantState(existingResultChild, context),
            replaceUnsupportedChildren: () => patchScrollableDetailsSection(existingChild, createdChild, context)
        })
    ) {
        changed = true;
    }
    applyKeyedScrollableStateWithBottomDefault(existingChild, preservedScroll, existingChild);
    return changed;
};

const shouldSkipCurrentDetailsPatch = (activity: HTMLElement, existingDetails: HTMLElement, createdDetails: HTMLElement): boolean => {
    const createdSignature = readInlineActivityDetailsRootSignature(createdDetails);
    const existingSignature = readInlineActivityDetailsRootSignature(existingDetails);
    return createdSignature !== null && existingSignature === createdSignature && inlineActivityDetailsSignatureIsCurrent(activity, existingDetails);
};

const patchInlineActivityDetailsContent = (existingDetails: HTMLElement, createdDetails: HTMLElement, patchActivity: ActivityPatchHandler, context: ActivityPatchContext, applyStreamingReveal: boolean): boolean => {
    let changed = syncElementShell({ target: existingDetails, source: createdDetails });

    const existingThinking = resolveDirectThinkingPhase(existingDetails);
    const createdThinking = resolveDirectThinkingPhase(createdDetails);
    if (existingThinking || createdThinking) {
        const preservedDetailsScroll = readKeyedScrollableState(existingDetails);
        if (!existingThinking || !createdThinking) {
            const patched = patchElementChildren(existingDetails, createdDetails, context);
            applyKeyedScrollableStateWithBottomDefault(existingDetails, preservedDetailsScroll, existingDetails);
            return patched;
        }
        if (patchElementChildren(existingThinking, createdThinking, context)) {
            changed = true;
        }
        applyKeyedScrollableStateWithBottomDefault(existingDetails, preservedDetailsScroll, existingDetails);
        return changed;
    }

    const preservedDetailsScroll = readKeyedScrollableState(existingDetails);
    if (
        patchOrderedChildren({
            existingParent: existingDetails,
            createdParent: createdDetails,
            resolveChildKey: resolveSectionType,
            insertChild: (parent, child, anchor) => insertClonedElementWithAssistantState(parent, child, anchor, context),
            patchChild: (existingChild, createdChild, sectionType) => {
                const subagentResultPatched = sectionType === 'result' ? patchSubagentResultSection(existingChild, createdChild, patchActivity, context, applyStreamingReveal) : null;
                if (subagentResultPatched !== null) {
                    return subagentResultPatched;
                }
                if (sectionType === 'result') {
                    return patchToolResultSection(existingChild, createdChild, context);
                }
                if (sectionType === 'args' || sectionType === 'diffs') {
                    return patchScrollableDetailsSection(existingChild, createdChild, context);
                }
                return patchElementChildren(existingChild, createdChild, context);
            },
            removeChild: (existingChild) => removeElementWithAssistantState(existingChild, context),
            replaceUnsupportedChildren: () => patchElementChildren(existingDetails, createdDetails, context)
        })
    ) {
        changed = true;
    }
    applyKeyedScrollableStateWithBottomDefault(existingDetails, preservedDetailsScroll, existingDetails);
    return changed;
};

const patchToolDetailsMarkup = (inputArguments: { existing: HTMLElement; created: HTMLElement; patchActivity: ActivityPatchHandler; assistantDomState: ActivityPatchContext['assistantDomState']; preserveOpenDetails: boolean; applyStreamingReveal?: boolean }): boolean => {
    const existingDetails = resolveDirectInlineActivityDetailsRoot(inputArguments.existing);
    const createdDetails = resolveDirectInlineActivityDetailsRoot(inputArguments.created);
    if (!existingDetails && !createdDetails) {
        return false;
    }
    if (!createdDetails) {
        if (!existingDetails) {
            return false;
        }
        if (inputArguments.preserveOpenDetails && inputArguments.existing.getAttribute('data-collapsed') !== 'true' && detailsRootHasPopulatedContent(existingDetails)) {
            return false;
        }
        removeElementWithAssistantState(existingDetails, { assistantDomState: inputArguments.assistantDomState });
        inputArguments.existing.removeAttribute('data-collapsing');
        inputArguments.existing.setAttribute('data-collapsed', 'true');
        return true;
    }
    if (!existingDetails) {
        const assistantDomState = resolveAssistantDomStateForPatch(inputArguments.existing, inputArguments.assistantDomState);
        if (assistantDomState) {
            insertOrReplaceAssistantDomChild({ parent: inputArguments.existing, element: createdDetails, anchor: null, state: assistantDomState });
        } else {
            inputArguments.existing.appendChild(createdDetails);
        }
        return true;
    }
    if (shouldSkipCurrentDetailsPatch(inputArguments.existing, existingDetails, createdDetails)) {
        return false;
    }
    return patchInlineActivityDetailsContent(existingDetails, createdDetails, inputArguments.patchActivity, { assistantDomState: inputArguments.assistantDomState }, inputArguments.applyStreamingReveal === true);
};

export { patchInlineActivityDetailsContent, patchToolDetailsMarkup };
