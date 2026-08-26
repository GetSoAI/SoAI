/* SoAI - DOM syncing for comparison-turn carousels (navigation, height, and chevrons) [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnCarouselController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import type { ActiveComparisonRun } from '@features/chat/public.ts';
import { parseNonNegativeIntegerAttribute } from '@pages/chat/widgets/comparisonturn/comparisonTurnDomParsingController.ts';
import { CHAT_COMPARISON_MESSAGE_SELECTOR, CHAT_COMPARISON_TURN_SELECTOR, CHAT_COMPARISON_TURN_SLIDE_SELECTOR, CHAT_COMPARISON_TURN_TRACK_SELECTOR, CHAT_COMPARISON_TURN_VIEWPORT_SELECTOR, CHEVRON_NEXT_SELECTOR, CHEVRON_PREV_SELECTOR } from '@pages/chat/widgets/comparisonturn/comparisonTurnDomSelectorsController.ts';
import { ComparisonTurnCarouselInteractionController } from '@pages/chat/widgets/comparisonturn/comparisonTurnCarouselInteractionController.ts';
import { ComparisonTurnCarouselTransitionController } from '@pages/chat/widgets/comparisonturn/comparisonTurnCarouselTransitionController.ts';
import { ComparisonTurnCarouselResizeObserverController } from '@pages/chat/widgets/comparisonturn/comparisonTurnCarouselResizeObserverController.ts';
import { ComparisonTurnCarouselViewportHeightCache } from '@pages/chat/widgets/comparisonturn/comparisonTurnCarouselViewportHeightCacheController.ts';
import type { ComparisonTurnSelectionController } from '@pages/chat/widgets/comparisonturn/comparisonTurnSelectionController.ts';

type ChevronButtonState = { assistantTurnTimestamp: number; activeIndex: number; navTotal: number; enabled: boolean };

const resolveViewport = (root: HTMLElement): HTMLElement | null => {
    const viewport = dom.resolve(CHAT_COMPARISON_TURN_VIEWPORT_SELECTOR, root);
    return viewport instanceof HTMLElement ? viewport : null;
};

const resolveTrack = (root: HTMLElement): HTMLElement | null => {
    const track = dom.resolve(CHAT_COMPARISON_TURN_TRACK_SELECTOR, root);
    return track instanceof HTMLElement ? track : null;
};

const resolveSlides = (track: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(CHAT_COMPARISON_TURN_SLIDE_SELECTOR, track).filter((node): node is HTMLElement => node instanceof HTMLElement && parseNonNegativeIntegerAttribute(node.getAttribute('data-comparison-slide-index'), 'data-comparison-slide-index') !== null);
};

const syncChevronButtonState = (button: Element | null, state: ChevronButtonState): void => {
    if (!(button instanceof HTMLButtonElement)) {
        return;
    }
    button.hidden = !state.enabled;
    button.disabled = !state.enabled;
    button.setAttribute('aria-hidden', state.enabled ? 'false' : 'true');
    button.setAttribute('data-assistant-turn-ts', String(state.assistantTurnTimestamp));
    button.setAttribute('data-comparison-active-variant-index', String(state.activeIndex));
    button.setAttribute('data-comparison-variant-total', String(state.navTotal));
};

class ComparisonTurnCarouselController {
    readonly #viewportHeightCache = new ComparisonTurnCarouselViewportHeightCache();
    readonly #isStreamingTurnByRoot = new Map<HTMLElement, boolean>();
    readonly #interactions = new ComparisonTurnCarouselInteractionController();
    readonly #transitionController: ComparisonTurnCarouselTransitionController;
    readonly #activeSlideObserver: ComparisonTurnCarouselResizeObserverController;

    constructor(timers: { setTimer: (functionValue: () => void, delayMs: number) => number; clearTimer: (timerId: number) => void }) {
        this.#transitionController = new ComparisonTurnCarouselTransitionController(timers);
        this.#activeSlideObserver = new ComparisonTurnCarouselResizeObserverController((root, viewport, slide) => this.#handleActiveSlideResize(root, viewport, slide));
    }

    dispose(): void {
        this.#activeSlideObserver.dispose();
        this.#interactions.dispose();
        this.#transitionController.dispose();
        this.#viewportHeightCache.dispose();
        this.#isStreamingTurnByRoot.clear();
    }

    syncCarousels(container: Element, inputArguments: { isCurrentStreaming: boolean; activeComparisonRun: ActiveComparisonRun | null }, selection: ComparisonTurnSelectionController): void {
        const roots = dom.resolveAll(CHAT_COMPARISON_TURN_SELECTOR, container).filter((node): node is HTMLElement => node instanceof HTMLElement);
        const knownRoots = new Set<HTMLElement>(roots);
        this.#activeSlideObserver.pruneKnownRoots(knownRoots);
        this.#interactions.pruneKnownRoots(knownRoots);
        this.#transitionController.pruneKnownRoots(knownRoots);
        this.#viewportHeightCache.pruneKnownRoots(knownRoots);
        for (const root of Array.from(this.#isStreamingTurnByRoot.keys())) {
            if (!root.isConnected || !knownRoots.has(root)) {
                this.#isStreamingTurnByRoot.delete(root);
            }
        }

        for (const root of roots) {
            const assistantTurnTimestamp = parseNonNegativeIntegerAttribute(root.getAttribute('data-assistant-turn-ts'), 'data-assistant-turn-ts');
            const slideCount = parseNonNegativeIntegerAttribute(root.getAttribute('data-comparison-variant-total'), 'data-comparison-variant-total');
            if (assistantTurnTimestamp === null || slideCount === null || slideCount <= 0) {
                continue;
            }
            const isStreamingTurn = Boolean(inputArguments.isCurrentStreaming && inputArguments.activeComparisonRun && inputArguments.activeComparisonRun.assistantTurnTimestamp === assistantTurnTimestamp);
            this.#isStreamingTurnByRoot.set(root, isStreamingTurn);
            this.#syncRoot(root, { assistantTurnTimestamp, slideCount }, selection);
        }
    }

    #readSlideIndex(slide: HTMLElement): number {
        const slideIndex = parseNonNegativeIntegerAttribute(slide.getAttribute('data-comparison-slide-index'), 'data-comparison-slide-index');
        return slideIndex ?? 0;
    }

    #measureElementHeight(element: HTMLElement): number {
        const rect = measureLayoutBox(element);
        const raw = rect.height;
        if (!Number.isFinite(raw) || raw <= 0) {
            return 0;
        }
        return Math.max(0, Math.ceil(raw));
    }

    #resolveSlideHeight(track: HTMLElement, slideIndex: number): number {
        const selector = `${CHAT_COMPARISON_TURN_SLIDE_SELECTOR}[data-comparison-slide-index="${CSS.escape(String(slideIndex))}"]`;
        const slide = dom.resolve(selector, track);
        if (!(slide instanceof HTMLElement)) {
            return 0;
        }
        return this.#measureElementHeight(slide);
    }

    #setCarouselViewportHeight(root: HTMLElement, viewport: HTMLElement, height: number): void {
        if (height <= 0) {
            return;
        }
        const value = `${String(height)}px`;
        if (this.#viewportHeightCache.readApplied(root) === height && viewport.style.getPropertyValue('height') === value && viewport.style.getPropertyPriority('height') === 'important') {
            return;
        }
        this.#viewportHeightCache.writeApplied(root, height);
        viewport.style.setProperty('height', value, 'important');
    }

    #syncRootFromDom(root: HTMLElement, selection: ComparisonTurnSelectionController): void {
        const assistantTurnTimestamp = parseNonNegativeIntegerAttribute(root.getAttribute('data-assistant-turn-ts'), 'data-assistant-turn-ts');
        const slideCount = parseNonNegativeIntegerAttribute(root.getAttribute('data-comparison-variant-total'), 'data-comparison-variant-total');
        if (assistantTurnTimestamp === null || slideCount === null || slideCount <= 0) {
            return;
        }
        this.#syncRoot(root, { assistantTurnTimestamp, slideCount }, selection);
    }

    #syncRoot(root: HTMLElement, attrs: { assistantTurnTimestamp: number; slideCount: number }, selection: ComparisonTurnSelectionController): void {
        const activeIndex = selection.resolveActiveVariantIndexForVariantCount(attrs.assistantTurnTimestamp, attrs.slideCount);
        const viewport = resolveViewport(root);
        const track = resolveTrack(root);
        if (!viewport || !track) {
            return;
        }

        const resolveVariantCountForSelection = (): number | null => {
            const canonicalSelector = `${CHAT_COMPARISON_MESSAGE_SELECTOR}[data-assistant-turn-ts="${CSS.escape(String(attrs.assistantTurnTimestamp))}"][data-model-variant-index="0"]`;
            const canonical = dom.resolve(canonicalSelector, root);
            if (!(canonical instanceof HTMLElement)) {
                return null;
            }
            return parseNonNegativeIntegerAttribute(canonical.getAttribute('data-comparison-variant-total'), 'data-comparison-variant-total');
        };

        this.#interactions.ensureMounted({
            root,
            viewport,
            assistantTurnTimestamp: attrs.assistantTurnTimestamp,
            resolveSlideCount: resolveVariantCountForSelection,
            selection,
            onSelectionChanged: () => this.#syncRootFromDom(root, selection)
        });

        const slides = resolveSlides(track);
        let activeSlide: HTMLElement | null = null;
        for (const slide of slides) {
            const slideIndex = this.#readSlideIndex(slide);
            const isActive = slideIndex === activeIndex;
            slide.setAttribute('aria-hidden', isActive ? 'false' : 'true');
            if (isActive) {
                slide.removeAttribute('inert');
                activeSlide = slide;
            } else {
                slide.setAttribute('inert', '');
            }
        }

        if (activeSlide instanceof HTMLElement) {
            const isStreamingTurn = this.#isStreamingTurnByRoot.get(root) ?? false;
            this.#transitionController.sync({
                root,
                track,
                activeIndex,
                resolveSlideHeight: (index) => this.#resolveSlideHeight(track, index),
                resolveCachedHeight: (index) => this.#viewportHeightCache.read(root, index),
                setViewportHeight: (height) => this.#setCarouselViewportHeight(root, viewport, height),
                settleViewportHeight: () => this.#syncCarouselViewportHeight(root, viewport, activeSlide, { isStreamingTurn, slideIndex: activeIndex })
            });
            this.#activeSlideObserver.sync(root, viewport, activeSlide);
            this.#syncCarouselChevronState(root, attrs.assistantTurnTimestamp, activeIndex);
        }

        if (root.getAttribute('data-comparison-mounted') !== 'true') {
            dom.setAttribute(root, 'data-comparison-mounted', 'true');
        }
    }

    #syncCarouselChevronState(root: HTMLElement, assistantTurnTimestamp: number, activeIndex: number): void {
        const activeAssistantSelector = `${CHAT_COMPARISON_MESSAGE_SELECTOR}[data-assistant-turn-ts="${CSS.escape(String(assistantTurnTimestamp))}"][data-model-variant-index="${CSS.escape(String(activeIndex))}"]`;
        const activeAssistantRoot = dom.resolve(activeAssistantSelector, root);
        if (!(activeAssistantRoot instanceof HTMLElement)) {
            return;
        }

        activeAssistantRoot.setAttribute('data-comparison-active-variant-index', String(activeIndex));
        const navTotal = parseNonNegativeIntegerAttribute(activeAssistantRoot.getAttribute('data-comparison-variant-total'), 'data-comparison-variant-total') ?? 1;
        const maxIndex = Math.max(0, navTotal - 1);
        syncChevronButtonState(dom.resolve(CHEVRON_PREV_SELECTOR, activeAssistantRoot), { assistantTurnTimestamp, activeIndex, navTotal, enabled: activeIndex > 0 });
        syncChevronButtonState(dom.resolve(CHEVRON_NEXT_SELECTOR, activeAssistantRoot), { assistantTurnTimestamp, activeIndex, navTotal, enabled: activeIndex < maxIndex });
    }

    #syncCarouselViewportHeight(root: HTMLElement, viewport: HTMLElement, activeSlide: HTMLElement, inputArguments: { isStreamingTurn: boolean; slideIndex: number }): void {
        const measured = this.#measureElementHeight(activeSlide);
        const previous = this.#viewportHeightCache.read(root, inputArguments.slideIndex);
        const nextHeight = inputArguments.isStreamingTurn ? Math.max(previous, measured) : measured;
        if (previous !== nextHeight) {
            this.#viewportHeightCache.write(root, inputArguments.slideIndex, nextHeight);
        }
        this.#setCarouselViewportHeight(root, viewport, nextHeight);
    }

    #handleActiveSlideResize(root: HTMLElement, viewport: HTMLElement, activeSlide: HTMLElement): void {
        const slideIndex = this.#readSlideIndex(activeSlide);
        const measured = this.#measureElementHeight(activeSlide);
        const previous = this.#viewportHeightCache.read(root, slideIndex);
        const isStreamingTurn = this.#isStreamingTurnByRoot.get(root) ?? false;
        if (this.#transitionController.isLocked(root)) {
            const lockedBaseline = this.#viewportHeightCache.readApplied(root) || this.#measureElementHeight(viewport);
            this.#setCarouselViewportHeight(root, viewport, Math.max(lockedBaseline, measured));
            if (measured > previous) this.#viewportHeightCache.write(root, slideIndex, measured);
            return;
        }
        const nextHeight = isStreamingTurn ? Math.max(previous, measured) : measured;
        if (previous === nextHeight) return;
        this.#viewportHeightCache.write(root, slideIndex, nextHeight);
        this.#setCarouselViewportHeight(root, viewport, nextHeight);
    }
}

export { ComparisonTurnCarouselController };
