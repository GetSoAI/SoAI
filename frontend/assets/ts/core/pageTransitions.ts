/* SoAI - Shared frontend page transitions [frontend/assets/ts/core/pageTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, DomObserver } from '@core/dom/dom.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { getWindow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFunction, isThenable } from '@core/typeGuards.ts';

const PAGE_TRANSITIONING_IN = 'page-transitioning-in';
const PAGE_CONTENT_READY = 'page-content-ready';
const PAGE_TRANSITION_SURFACE_SELECTOR = '[data-page-transition-surface="true"]';
const PAGE_TRANSITION_MODE_ATTRIBUTE = 'data-page-transition-mode';
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

const resolveAnimationCandidates = async (element: Element, subtree: boolean): Promise<Animation[]> => {
    let candidates = readAnimations(element, subtree);
    if (candidates.length > 0) {
        return candidates;
    }
    await DomObserver.animationFrame();
    candidates = readAnimations(element, subtree);
    return candidates;
};

interface AbortWaitTask {
    task: Promise<string>;
    cleanup: () => void;
}

const createAbortWaitTask = (signal: AbortSignal | null): AbortWaitTask | null => {
    if (!signal) {
        return null;
    }
    if (signal.aborted) {
        return { task: Promise.resolve('aborted'), cleanup: () => {} };
    }
    let abortHandler: (() => void) | null = null;
    const task = new Promise<string>((resolve) => {
        abortHandler = () => resolve('aborted');
        signal.addEventListener('abort', abortHandler, { once: true });
    });
    const cleanup = (): void => {
        if (abortHandler) {
            signal.removeEventListener('abort', abortHandler);
            abortHandler = null;
        }
    };
    return { task, cleanup };
};

const waitForElementAnimations = async (element: Element, { ensureStarted = true, subtree = false, signal = null, requireAnimation = false }: { ensureStarted?: boolean; subtree?: boolean; signal?: AbortSignal | null; requireAnimation?: boolean } = {}): Promise<void> => {
    if (!element) {
        throw new Error('Page transition animation target is required');
    }
    if (signal?.aborted) {
        return;
    }

    if (ensureStarted) {
        await DomObserver.animationFrame();
    }
    if (signal?.aborted) {
        return;
    }

    const windowRef = getWindow();
    const animationCandidates = await resolveAnimationCandidates(element, subtree);
    if (signal?.aborted) {
        return;
    }
    const waitTasks: Promise<void>[] = [];

    let animationTaskCount = 0;
    for (const candidate of animationCandidates) {
        const finished = candidate.finished;
        if (!isThenable(finished)) {
            continue;
        }
        animationTaskCount += 1;
        waitTasks.push(Promise.resolve(finished).then(() => undefined));
    }

    if (requireAnimation && animationTaskCount === 0) {
        throw new Error(`Page transition target ${element.nodeName} did not start an animation`);
    }

    if (waitTasks.length === 0) {
        return;
    }

    let timeoutId: number | null = null;
    const timeoutTask: Promise<string> = new Promise((resolve) => {
        timeoutId = windowRef.setTimeout(() => resolve('timeout'), ANIMATION_WAIT_TIMEOUT_MS);
    });
    const finishedTask: Promise<string> = Promise.all(waitTasks).then(() => 'done');
    const raceTasks: Promise<string>[] = [finishedTask, timeoutTask];
    const abortTask = createAbortWaitTask(signal);
    if (abortTask) {
        raceTasks.push(abortTask.task);
    }

    try {
        const outcome = await Promise.race(raceTasks);
        if (outcome === 'timeout') {
            throw new Error(`Page transition animation timed out after ${ANIMATION_WAIT_TIMEOUT_MS}ms for ${element.nodeName}`);
        }
    } finally {
        abortTask?.cleanup();
        if (timeoutId !== null) {
            windowRef.clearTimeout(timeoutId);
            timeoutId = null;
        }
    }
};

export { PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN, PAGE_TRANSITION_MODE_ATTRIBUTE, isReduceMotionsEnabled, resolveActiveSection, requirePageTransitionSurface, revealMountedPageSection, waitForElementAnimations };
export type { PageTransitionSurfaceResolution };
