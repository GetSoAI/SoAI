/* SoAI - Pane workspace motion for appearing, disappearing and resizing panes [frontend/assets/ts/core/pagepanes/motion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { runCleanupStepCollectingFailure } from '@core/lifecycle/cleanup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { isPageContentAvailable } from '@core/layout/pageContentInteractivity.ts';
import { choreographPagePanes } from '@core/pagepanes/motionChoreography.ts';
import { measurePagePaneItems } from '@core/pagepanes/motionContent.ts';
import { stagePagePaneGhosts } from '@core/pagepanes/motionGhosts.ts';
import { PAGE_PANE_HELD_ATTRIBUTE, PAGE_PANE_RESERVE_ATTRIBUTE, PAGE_PANE_RESTORING_ATTRIBUTE, applyPagePaneSplit, endPagePaneTransition, isPagePaneDisplayed, isPagePanePresent, listPagePaneRoots, measurePagePaneBoxes, measurePagePaneOutletOffsets, readPagePaneDuration, splitTargets, transitions, type PagePaneTransition } from '@core/pagepanes/motionStage.ts';

const canAnimatePagePanes = (container: HTMLElement): boolean => {
    const documentRef = container.ownerDocument;
    return container.isConnected && !container.hasAttribute(PAGE_PANE_RESTORING_ATTRIBUTE) && typeof container.animate === 'function' && isPageContentAvailable(container) && documentRef.visibilityState === 'visible' && !isReducedAnimationScope(container) && readPagePaneDuration(container, '--motion-pane-reflow-duration') > 0;
};

const createPagePaneTransition = (container: HTMLElement, before: ReadonlyMap<HTMLElement, GeometryBox>, closing: HTMLElement | null): PagePaneTransition => ({
    container,
    bounds: measureLayoutBox(container),
    before,
    outlets: measurePagePaneOutletOffsets(before),
    items: new Map(Array.from(before.keys(), (root) => [root, measurePagePaneItems(root)])),
    after: new Map(),
    holds: new Set(),
    choreography: [],
    deferred: [],
    exiting: new Set(),
    layers: new Map(),
    ghostLayers: [],
    closing,
    settled: new Set(),
    controller: new AbortController(),
    resources: new ResourceTracker(),
    previousSplit: splitTargets.get(container),
    finished: false,
    phase: 'frozen',
    readiness: null,
    deadline: null
});

const syncPagePaneSplit = (container: HTMLElement, split: boolean): void => {
    splitTargets.set(container, split);
    const transition = transitions.get(container);
    applyPagePaneSplit(container, transition?.phase === 'frozen' ? new Set(transition.before.keys()) : (transition?.exiting ?? null));
};

const capturePagePaneLayout = (container: HTMLElement, roots: readonly HTMLElement[]): PagePaneTransition | null => {
    const current = transitions.get(container);
    if (!canAnimatePagePanes(container)) {
        if (current) endPagePaneTransition(current, current.closing === null);
        return null;
    }
    if (current?.closing) return null;
    if (current) endPagePaneTransition(current, current.closing === null);
    const before = measurePagePaneBoxes(roots, isPagePaneDisplayed);
    if (before.size === 0) return null;
    const transition = createPagePaneTransition(container, before, null);
    transitions.set(container, transition);
    try {
        stagePagePaneGhosts(transition, before.keys());
        return transition;
    } catch (error) {
        const failures = [ensureError(error)];
        runCleanupStepCollectingFailure(() => endPagePaneTransition(transition, false), failures);
        errorHandler.warn('PagePaneMotion', 'Pane layout motion unavailable', new AggregateError(failures));
        return null;
    }
};

const playPagePaneLayout = (transition: PagePaneTransition, roots: readonly HTMLElement[]): void => {
    if (transitions.get(transition.container) !== transition || transition.phase !== 'frozen') return;
    try {
        choreographPagePanes(transition, roots);
    } catch (error) {
        const failures = [ensureError(error)];
        runCleanupStepCollectingFailure(() => endPagePaneTransition(transition, false), failures);
        errorHandler.warn('PagePaneMotion', 'Pane choreography unavailable', new AggregateError(failures));
    }
};

const relayoutPagePanes = (container: HTMLElement, change: () => void): void => {
    const roots = listPagePaneRoots(container);
    const transition = capturePagePaneLayout(container, roots);
    change();
    splitTargets.set(container, roots.filter(isPagePanePresent).length > 1);
    if (transition) playPagePaneLayout(transition, roots);
    else applyPagePaneSplit(container);
};

const releasePagePaneExit =
    (root: HTMLElement): (() => void) =>
    () => {
        if (root.getAttribute(PAGE_PANE_HELD_ATTRIBUTE) !== 'gone') return;
        const container = root.parentElement;
        const clear = (): void => root.removeAttribute(PAGE_PANE_HELD_ATTRIBUTE);
        if (container && !root.hidden && !transitions.has(container)) relayoutPagePanes(container, clear);
        else clear();
    };

const joinPagePaneExit = (transition: PagePaneTransition, signal: AbortSignal, release: () => void): Promise<() => void> => {
    const completion = createDeferred<() => void>();
    const settled = (completed: boolean): void => {
        signal.removeEventListener('abort', aborted);
        transition.settled.delete(settled);
        if (completed && !signal.aborted) completion.resolve(release);
        else completion.reject(createAbortError('Pane close preparation cancelled'));
    };
    const aborted = (): void => {
        settled(false);
        if (transition.settled.size === 0) endPagePaneTransition(transition, false);
    };
    transition.settled.add(settled);
    signal.addEventListener('abort', aborted, { once: true });
    if (signal.aborted) aborted();
    return completion.promise;
};

const preparePagePaneExit = (root: HTMLElement, signal: AbortSignal): Promise<() => void> => {
    throwIfAborted(signal);
    const container = root.parentElement;
    const idle = (): void => undefined;
    const release = releasePagePaneExit(root);
    if (root.getAttribute(PAGE_PANE_HELD_ATTRIBUTE) === 'gone') return Promise.resolve(release);
    if (container === null || signal.aborted || !canAnimatePagePanes(container)) return Promise.resolve(idle);
    const current = transitions.get(container);
    if (current?.closing === root) return joinPagePaneExit(current, signal, release);
    if (current) endPagePaneTransition(current, current.closing === null);
    const roots = listPagePaneRoots(container);
    const before = measurePagePaneBoxes(roots, isPagePaneDisplayed);
    if (!before.has(root)) return Promise.resolve(idle);
    const transition = createPagePaneTransition(container, before, root);
    transitions.set(container, transition);
    const settled = joinPagePaneExit(transition, signal, release);
    try {
        stagePagePaneGhosts(
            transition,
            Array.from(before.keys()).filter((candidate) => candidate !== root)
        );
        splitTargets.set(container, roots.filter((candidate) => candidate !== root && before.has(candidate)).length > 1);
        choreographPagePanes(transition, roots);
    } catch (error) {
        const failures = [ensureError(error)];
        runCleanupStepCollectingFailure(() => endPagePaneTransition(transition), failures);
        errorHandler.warn('PagePaneMotion', 'Pane exit motion unavailable', new AggregateError(failures));
    }
    return settled;
};

const anticipatePagePaneExit = (root: HTMLElement): (() => void) => {
    const controller = new AbortController();
    let release: (() => void) | null = null;
    const restore = (): void => {
        const container = root.parentElement;
        if (release === null || container === null || root.getAttribute(PAGE_PANE_HELD_ATTRIBUTE) !== 'gone') return;
        relayoutPagePanes(container, release);
    };
    void preparePagePaneExit(root, controller.signal)
        .then((completed) => {
            release = completed;
            if (controller.signal.aborted) restore();
        })
        .catch((error) => {
            if (!isAbortError(error)) errorHandler.warn('PagePaneMotion', 'Pane exit anticipation failed', ensureError(error));
        });
    return () => {
        controller.abort();
        restore();
    };
};

const PAGE_PANE_RESERVED_COLUMN_PROPERTY = '--page-pane-reserved-column';

const reservePagePanes = (container: HTMLElement, primary: HTMLElement, count: number, column: number): (() => void) => {
    if (count < 2) return () => undefined;
    const current = transitions.get(container);
    if (current) endPagePaneTransition(current, current.closing === null);
    container.setAttribute(PAGE_PANE_RESTORING_ATTRIBUTE, '');
    container.setAttribute(PAGE_PANE_RESERVE_ATTRIBUTE, String(count));
    dom.setStyles(primary, { [PAGE_PANE_RESERVED_COLUMN_PROPERTY]: String(column) });
    applyPagePaneSplit(container);
    return () => {
        if (!container.hasAttribute(PAGE_PANE_RESERVE_ATTRIBUTE)) return;
        container.removeAttribute(PAGE_PANE_RESTORING_ATTRIBUTE);
        relayoutPagePanes(container, () => {
            container.removeAttribute(PAGE_PANE_RESERVE_ATTRIBUTE);
            dom.setStyles(primary, { [PAGE_PANE_RESERVED_COLUMN_PROPERTY]: null });
        });
    };
};

export { anticipatePagePaneExit, reservePagePanes, capturePagePaneLayout, playPagePaneLayout, preparePagePaneExit, syncPagePaneSplit };
