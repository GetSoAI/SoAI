/* SoAI - Comparison-turn entry DOM mutation ownership [frontend/assets/ts/features/chat/message/comparisonTurnEntryMutation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { optionalNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { haveEqualChildNodes, resolveHTMLElement, syncAttributes, syncClass } from '@core/dom/patching.ts';
import type { ComparisonTurnRenderEntry } from '@features/chat/conversation/rendering/conversationEntries.ts';
import { resolveAssistantMutationPostRenderType } from '@features/chat/message/assistantMutationPostRenderPolicy.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { canPatchAssistantMessageTextInPlace } from '@features/chat/message/assistantMessageTextPatching.ts';
import { applyAssistantRenderTransaction } from '@features/chat/message/assistantRenderTransaction.ts';
import type { AssistantViewportStabilityScope } from '@features/chat/message/assistantViewportStability.ts';
import type { ChatPostRenderRequestType } from '@features/chat/message/types.ts';
import { parseRenderedMarkupRoot } from '@features/chat/message/renderedMarkupRoot.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type PatchResult = {
    changed: boolean;
    postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[];
};

type ExistingComparisonSlides = {
    byIndex: Map<string, HTMLElement>;
    unstableSlides: Element[];
};

type AssistantSlide = {
    content: HTMLElement;
    root: HTMLElement;
};

type IndexedComparisonSlide = {
    index: string;
    slide: HTMLElement;
};

const PRESERVED_ROOT_ATTRIBUTE_NAMES = new Set<string>(['data-id']);

const resolveSlideIndex = (slide: HTMLElement): string | null => {
    const slideIndex = optionalNonNegativeIntegerAttribute(slide, 'data-comparison-slide-index', 'Chat comparison turn slide index');
    if (slideIndex === null) {
        return null;
    }
    return String(slideIndex);
};

const resolveAssistantSlideContent = (slide: HTMLElement): HTMLElement | null => {
    const candidate = dom.resolve(':scope > .chat-comparison-turn-slide-content', slide);
    return candidate instanceof HTMLElement ? candidate : null;
};

const resolveAssistantSlide = (slide: HTMLElement): AssistantSlide | null => {
    const content = resolveAssistantSlideContent(slide);
    if (content === null) {
        return null;
    }
    const candidate = dom.resolve(':scope > .chat-message.assistant', content);
    if (!(candidate instanceof HTMLElement)) {
        return null;
    }
    return { content, root: candidate };
};

const resolveIndexedComparisonSlides = (track: HTMLElement): IndexedComparisonSlide[] => {
    const indexedSlides: IndexedComparisonSlide[] = [];
    const indexes = new Set<string>();
    for (const candidate of dom.resolveAll(':scope > .chat-comparison-turn-slide', track)) {
        if (!(candidate instanceof HTMLElement)) {
            continue;
        }
        const index = resolveSlideIndex(candidate);
        if (index !== null) {
            if (indexes.has(index)) {
                throw new Error('Chat comparison turn reconcile requires unique slide indexes.');
            }
            indexes.add(index);
            indexedSlides.push({ index, slide: candidate });
        }
    }
    return indexedSlides;
};

const resolveVariantEntry = (entry: ComparisonTurnRenderEntry, slideIndex: string): ComparisonTurnRenderEntry['variants'][number] | null => {
    for (const variant of entry.variants) {
        if (String(variant.variantIndex) === slideIndex) {
            return variant;
        }
    }
    return null;
};

const resolveExistingComparisonSlides = (track: HTMLElement): ExistingComparisonSlides => {
    const byIndex = new Map<string, HTMLElement>();
    const unstableSlides: Element[] = [];
    const slides = dom.resolveAll(':scope > .chat-comparison-turn-slide', track);
    for (const slide of slides) {
        if (!(slide instanceof HTMLElement)) {
            unstableSlides.push(slide);
            continue;
        }
        const index = resolveSlideIndex(slide);
        if (index === null || byIndex.has(index)) {
            unstableSlides.push(slide);
            continue;
        }
        byIndex.set(index, slide);
    }
    return { byIndex, unstableSlides };
};

const validateAssistantSlide = (slide: HTMLElement): AssistantSlide | null => {
    const assistant = resolveAssistantSlide(slide);
    if (assistant === null) {
        return null;
    }
    const parts = resolveAssistantMessageParts(assistant.root);
    if (!parts || !canPatchAssistantMessageTextInPlace(parts.text, parts.text)) {
        throw new Error('Chat comparison turn reconcile requires canonical keyed assistant bodies.');
    }
    return assistant;
};

const validateComparisonSlidePatches = (existingSlides: ExistingComparisonSlides, createdSlides: readonly IndexedComparisonSlide[], entry: ComparisonTurnRenderEntry): void => {
    for (const createdSlide of createdSlides) {
        const createdAssistant = validateAssistantSlide(createdSlide.slide);
        const existingSlide = existingSlides.byIndex.get(createdSlide.index) ?? null;
        const existingAssistant = existingSlide === null ? null : validateAssistantSlide(existingSlide);
        if (createdAssistant && existingAssistant && resolveVariantEntry(entry, createdSlide.index) === null) {
            throw new Error('Comparison turn assistant patch requires a rendered assistant variant.');
        }
    }
};

const applySlidePatch = (inputArguments: { existingSlide: HTMLElement; createdSlide: HTMLElement; isCurrentStreaming: boolean; entry: ComparisonTurnRenderEntry; slideIndex: string; viewportStabilityScope: AssistantViewportStabilityScope }): PatchResult => {
    const existingAssistant = resolveAssistantSlide(inputArguments.existingSlide);
    const createdAssistant = resolveAssistantSlide(inputArguments.createdSlide);
    let changed = false;
    const postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[] = [];

    if (syncClass(inputArguments.existingSlide, inputArguments.createdSlide)) {
        changed = true;
    }
    if (syncAttributes({ target: inputArguments.existingSlide, source: inputArguments.createdSlide })) {
        changed = true;
    }

    if (existingAssistant && createdAssistant) {
        const variant = resolveVariantEntry(inputArguments.entry, inputArguments.slideIndex);
        if (variant === null || variant.message === null || variant.comparisonTurn === null) {
            throw new Error('Comparison turn assistant patch requires a rendered assistant variant.');
        }
        const applied = applyAssistantRenderTransaction({
            existingMessageRoot: existingAssistant.root,
            replacement: createdAssistant.root,
            intent: inputArguments.isCurrentStreaming && variant.isActiveStreamingEntry ? 'streamingChrome' : 'idleRefresh',
            messageDomId: variant.domId ?? existingAssistant.root.getAttribute('data-id') ?? '',
            message: variant.message,
            comparisonTurn: variant.comparisonTurn,
            viewportStabilityScope: inputArguments.viewportStabilityScope
        });
        if (syncClass(existingAssistant.content, createdAssistant.content)) {
            changed = true;
        }
        if (syncAttributes({ target: existingAssistant.content, source: createdAssistant.content })) {
            changed = true;
        }
        if (applied.changed) {
            changed = true;
        }
        const postRenderType = resolveAssistantMutationPostRenderType({
            changed: applied.changed,
            requiresPostRender: applied.requiresPostRender,
            surface: 'comparisonSlide'
        });
        if (postRenderType !== null) {
            postRenderRequests.push({ root: applied.root, type: postRenderType });
        }
        return { changed, postRenderRequests };
    }

    if (!existingAssistant && !createdAssistant) {
        if (!haveEqualChildNodes(inputArguments.existingSlide, inputArguments.createdSlide)) {
            inputArguments.existingSlide.replaceChildren(...Array.from(inputArguments.createdSlide.childNodes).map((node) => node.cloneNode(true)));
            changed = true;
        }
        return { changed, postRenderRequests };
    }

    inputArguments.existingSlide.replaceChildren(...Array.from(inputArguments.createdSlide.childNodes).map((node) => node.cloneNode(true)));
    changed = true;
    const insertedAssistant = resolveAssistantSlide(inputArguments.existingSlide);
    if (insertedAssistant) {
        postRenderRequests.push({ root: insertedAssistant.root, type: 'canonicalFull' });
    }
    return { changed, postRenderRequests };
};

const applyComparisonTurnEntryMutation = (inputArguments: { existingRoot: HTMLElement; nextMarkup: TrustedHtml; isCurrentStreaming: boolean; entry: ComparisonTurnRenderEntry; viewportStabilityScope: AssistantViewportStabilityScope }): PatchResult => {
    const created = parseRenderedMarkupRoot({
        documentRef: inputArguments.existingRoot.ownerDocument,
        nextMarkup: inputArguments.nextMarkup,
        context: inputArguments.existingRoot.ownerDocument,
        failureMessage: 'Chat comparison turn reconcile failed to parse rendered markup.'
    });
    if (!created.classList.contains('chat-comparison-turn')) {
        throw new Error('Chat comparison turn reconcile requires a .chat-comparison-turn root.');
    }

    const existingTrack = resolveHTMLElement(':scope > .chat-comparison-turn-viewport > .chat-comparison-turn-track', inputArguments.existingRoot);
    const createdTrack = resolveHTMLElement(':scope > .chat-comparison-turn-viewport > .chat-comparison-turn-track', created);
    if (!existingTrack || !createdTrack) {
        throw new Error('Chat comparison turn reconcile requires a canonical track DOM shape.');
    }

    const existingSlides = resolveExistingComparisonSlides(existingTrack);
    const createdSlides = resolveIndexedComparisonSlides(createdTrack);
    validateComparisonSlidePatches(existingSlides, createdSlides, inputArguments.entry);

    let changed = false;
    const postRenderRequests: { root: HTMLElement; type: ChatPostRenderRequestType }[] = [];
    if (syncClass(inputArguments.existingRoot, created)) {
        changed = true;
    }
    if (syncAttributes({ target: inputArguments.existingRoot, source: created, preservedAttributeNames: PRESERVED_ROOT_ATTRIBUTE_NAMES })) {
        changed = true;
    }

    let anchor: ChildNode | null = existingTrack.firstChild;
    const remaining = new Map(existingSlides.byIndex);
    for (const createdSlide of createdSlides) {
        let existingSlide = remaining.get(createdSlide.index) ?? null;
        if (!existingSlide) {
            const cloned = inputArguments.existingRoot.ownerDocument.importNode(createdSlide.slide, true);
            existingSlide = cloned;
            existingTrack.insertBefore(existingSlide, anchor);
            changed = true;
            const insertedAssistant = resolveAssistantSlide(existingSlide);
            if (insertedAssistant) {
                postRenderRequests.push({ root: insertedAssistant.root, type: 'canonicalFull' });
            }
        } else if (anchor !== existingSlide) {
            existingTrack.insertBefore(existingSlide, anchor);
            changed = true;
        } else {
            anchor = existingSlide.nextSibling;
        }

        const patch = applySlidePatch({
            existingSlide,
            createdSlide: createdSlide.slide,
            isCurrentStreaming: inputArguments.isCurrentStreaming,
            entry: inputArguments.entry,
            slideIndex: createdSlide.index,
            viewportStabilityScope: inputArguments.viewportStabilityScope
        });
        if (patch.changed) {
            changed = true;
        }
        postRenderRequests.push(...patch.postRenderRequests);
        remaining.delete(createdSlide.index);
        anchor = existingSlide.nextSibling;
    }

    if (remaining.size > 0) {
        for (const slide of remaining.values()) {
            slide.remove();
            changed = true;
        }
    }
    for (const slide of existingSlides.unstableSlides) {
        slide.remove();
        changed = true;
    }

    const uniquePostRenderRequests = new Map<HTMLElement, ChatPostRenderRequestType>();
    for (const request of postRenderRequests) {
        uniquePostRenderRequests.set(request.root, request.type);
    }

    return {
        changed,
        postRenderRequests: Array.from(uniquePostRenderRequests, ([root, type]) => ({ root, type }))
    };
};

export { applyComparisonTurnEntryMutation };
