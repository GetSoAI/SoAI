/* SoAI - Shared frontend page transitions [frontend/assets/ts/core/pageTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { isAbortError, raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';
import { awaitPresentationFrame } from '@core/runtime/animationFrames.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFunction, isThenable } from '@core/typeGuards.ts';

const PAGE_TRANSITIONING_IN = 'page-transitioning-in';
const PAGE_CONTENT_READY = 'page-content-ready';
const PAGE_TRANSITION_SURFACE_SELECTOR = '[data-page-transition-surface="true"]';
const PAGE_TRANSITION_MODE_ATTRIBUTE = 'data-page-transition-mode';
const PAGE_EXITING_ATTRIBUTE = 'data-page-exiting';
const ANIMATION_WAIT_TIMEOUT_MS = 1500;

interface PageTransitionSurfaceResolution {
    surface: Element;
    mode: 'section' | 'surface';
}

const isReduceMotionsEnabled = (): boolean => {
    return isReducedAnimationScope(dom.getDocument());
};

const resolveActiveSection = (container: Element): Element | null => {
    if (!container) {
        throw new Error('Container is required');
    }
    const selectors = [`[data-section].${PAGE_CONTENT_READY}`, `[data-section].${PAGE_TRANSITIONING_IN}`, '[data-section]'];
    for (const selector of selectors) {
        const section = dom.resolve(selector, container);
        if (section) {
            return section;
        }
    }
    return null;
};

const requirePageTransitionSurface = (section: Element): PageTransitionSurfaceResolution => {
    if (!section) {
        throw new Error('Page transition section is required');
    }
    const surfaces = dom.resolveAll(PAGE_TRANSITION_SURFACE_SELECTOR, section);
    if (section.matches(PAGE_TRANSITION_SURFACE_SELECTOR)) {
        surfaces.unshift(section);
    }
    if (surfaces.length > 1) {
        throw new Error(`Page section ${section.getAttribute('data-section') ?? section.nodeName} must define at most one page transition surface`);
    }
    const surface = surfaces[0];
    if (!surface) {
        throw new Error(`Page section ${section.getAttribute('data-section') ?? section.nodeName} must define one page transition surface`);
    }
    return {
        surface,
        mode: surface === section ? 'section' : 'surface'
    };
};

const revealMountedPageSection = (container: Element): void => {
    const section = resolveActiveSection(container);
    if (!section) {
        throw new Error('Direct page host reveal requires a mounted page section');
    }
    requirePageTransitionSurface(section);
    section.classList.remove(PAGE_TRANSITIONING_IN);
    section.classList.add(PAGE_CONTENT_READY);
    section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
};

const readAnimations = (element: Element, subtree: boolean): Animation[] => {
    const getAnimationsCandidate = element.getAnimations;
    if (!isFunction(getAnimationsCandidate)) {
        throw new Error(`Page transition target ${element.nodeName} does not expose getAnimations()`);
    }
    try {
        return element.getAnimations({ subtree });
    } catch (error) {
        const runtimeError = ensureError(error);
        throw new Error(`Page transition animation inspection failed: ${runtimeError.message}`);
    }
};

const resolveAnimationCandidates = async (element: Element, subtree: boolean, signal: AbortSignal): Promise<Animation[]> => {
    let candidates = readAnimations(element, subtree);
    if (candidates.length > 0) {
        return candidates;
    }
    await awaitPresentationFrame(signal, 'Animation discovery aborted.');
    throwIfAborted(signal);
    candidates = readAnimations(element, subtree);
    return candidates;
};

const waitForElementAnimations = async (element: Element, { ensureStarted = true, subtree = false, signal = null, requireAnimation = false, animations = null }: { ensureStarted?: boolean; subtree?: boolean; signal?: AbortSignal | null; requireAnimation?: boolean; animations?: readonly Animation[] | null } = {}): Promise<void> => {
    if (!element) {
        throw new Error('Page transition animation target is required');
    }
    const document = element.ownerDocument;
    if (signal?.aborted || document.visibilityState === 'hidden') return;
    const timeoutMessage = `Page transition animation timed out after ${ANIMATION_WAIT_TIMEOUT_MS}ms for ${element.nodeName}`;
    const deadline = monotonicMs() + ANIMATION_WAIT_TIMEOUT_MS;
    const assertDeadline = (): void => {
        if (monotonicMs() >= deadline) throw new Error(timeoutMessage);
    };
    const visibilityAbort = new AbortController();
    const onVisibilityChange = (): void => {
        if (document.visibilityState === 'hidden') visibilityAbort.abort();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    try {
        await runWithAbortSignalScope([signal, visibilityAbort.signal], (presentationSignal) =>
            withAbortableTimeout(
                (timeoutSignal) =>
                    runWithAbortSignalScope([presentationSignal, timeoutSignal], async (waitSignal) => {
                        throwIfAborted(waitSignal);
                        if (ensureStarted) await awaitPresentationFrame(waitSignal, 'Animation startup aborted.');
                        throwIfAborted(waitSignal);
                        const animationCandidates = animations ?? (await resolveAnimationCandidates(element, subtree, waitSignal));
                        throwIfAborted(waitSignal);
                        assertDeadline();
                        const waitTasks: Promise<void>[] = [];
                        for (const candidate of animationCandidates) {
                            const finished = candidate.finished;
                            if (isThenable(finished)) waitTasks.push(Promise.resolve(finished).then(() => undefined));
                        }
                        if (requireAnimation && waitTasks.length === 0) {
                            throw new Error(`Page transition target ${element.nodeName} did not start an animation`);
                        }
                        await raceWithAbortSignal(Promise.all(waitTasks), waitSignal);
                        assertDeadline();
                    }),
                { timeoutMs: ANIMATION_WAIT_TIMEOUT_MS, timeoutMessage }
            )
        );
    } catch (error) {
        if (isAbortError(error) && (signal?.aborted || visibilityAbort.signal.aborted)) return;
        throw error;
    } finally {
        document.removeEventListener('visibilitychange', onVisibilityChange);
    }
};

export { PAGE_CONTENT_READY, PAGE_EXITING_ATTRIBUTE, PAGE_TRANSITIONING_IN, PAGE_TRANSITION_MODE_ATTRIBUTE, isReduceMotionsEnabled, resolveActiveSection, requirePageTransitionSurface, revealMountedPageSection, waitForElementAnimations };
export type { PageTransitionSurfaceResolution };
