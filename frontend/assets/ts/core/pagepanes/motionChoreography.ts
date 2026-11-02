/* SoAI - Compositor-only pane workspace choreography [frontend/assets/ts/core/pagepanes/motionChoreography.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { awaitPresentationFrame } from '@core/runtime/animationFrames.ts';
import { isAbortError, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isRtl } from '@core/layout/direction.ts';
import { dispatchPaneRelayout } from '@core/layout/paneRelayout.ts';
import { animatePagePaneGhosts } from '@core/pagepanes/motionGhosts.ts';
import { dom } from '@core/dom/dom.ts';
import { measureGridColumnTracks, measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { PAGE_PANE_LAYOUT_TOLERANCE_PX, PAGE_PANE_OUTLET_CLASS, applyPagePaneSplit, endPagePaneTransition, holdPagePane, isPagePaneDisplayed, isPagePaneLaidOut, listPagePaneRoots, measurePagePaneBoxes, measurePagePaneOutletOffsets, readPagePaneDuration, readPagePaneToken, transitions, type PagePaneTransition } from '@core/pagepanes/motionStage.ts';
import { animatePagePaneItems, measurePagePaneItems, type PagePaneItemPositions } from '@core/pagepanes/motionContent.ts';
import { collapsePagePaneSpan, resolvePagePaneAnchor, resolvePagePaneLayerMotion, toPagePaneSpan, type PagePaneAnchor, type PagePaneSpan } from '@core/pagepanes/motionWindows.ts';

const PAGE_PANE_ENTERING_PAGE_SELECTOR = ':scope > .page-pane-outlet > [data-section].page-transitioning-in';
const PAGE_PANE_READY_SELECTOR = ':scope > .page-pane-outlet > [data-section].page-content-ready';
const PAGE_PANE_CALM_FRAME_MS = 40;
const PAGE_PANE_CALM_FRAMES = 2;
const PAGE_PANE_CALM_LIMIT_MS = 120;

interface PagePaneWindowPlan {
    readonly origin: PagePaneSpan;
    readonly target: PagePaneSpan;
    readonly anchor: PagePaneAnchor;
}

const alignEnteringPages = (transition: PagePaneTransition): void => {
    for (const root of transition.after.keys()) {
        if (transition.before.has(root)) continue;
        for (const section of dom.resolveAll(PAGE_PANE_ENTERING_PAGE_SELECTOR, root)) {
            for (const animation of section.getAnimations({ subtree: true })) {
                if (animation instanceof CSSAnimation && animation.playState === 'running' && Number.isFinite(animation.effect?.getComputedTiming().endTime ?? Infinity)) animation.currentTime = 0;
            }
        }
    }
};

const awaitPagePaneCalm = async (transition: PagePaneTransition): Promise<void> => {
    const deadline = new AbortController();
    const timer = transition.resources.setTimeout(() => deadline.abort(), PAGE_PANE_CALM_LIMIT_MS);
    try {
        await runWithAbortSignalScope([transition.controller.signal, deadline.signal], async (signal) => {
            let previous: number | null = null;
            let calm = 0;
            while (calm < PAGE_PANE_CALM_FRAMES) {
                if ((await awaitPresentationFrame(signal, 'Pane motion cancelled')) === 'hidden') return;
                const time = monotonicMs();
                calm = previous !== null && time - previous <= PAGE_PANE_CALM_FRAME_MS ? calm + 1 : 0;
                previous = time;
            }
        });
    } catch (error) {
        if (!deadline.signal.aborted || !isAbortError(error)) throw error;
    } finally {
        transition.resources.clearTimeout(timer);
    }
    throwIfAborted(transition.controller.signal);
};

const resolvePagePaneAreas = (container: HTMLElement, boxes: ReadonlyMap<HTMLElement, GeometryBox>, rtl: boolean): Map<HTMLElement, PagePaneSpan> | null => {
    const tracks = measureGridColumnTracks(container);
    if (tracks === null || tracks.length !== boxes.size) return null;
    const areas = new Map<HTMLElement, PagePaneSpan>();
    for (const [root, box] of boxes) {
        const width = tracks[areas.size] ?? box.width;
        areas.set(root, rtl ? { left: box.right - width, right: box.right } : { left: box.left, right: box.left + width });
    }
    return areas;
};

const resolvePagePaneSeam = (container: HTMLElement, root: HTMLElement, spans: ReadonlyMap<HTMLElement, PagePaneSpan>, bounds: GeometryBox, rtl: boolean): number => {
    let seam = rtl ? bounds.right : bounds.left;
    for (const candidate of listPagePaneRoots(container)) {
        if (candidate === root) break;
        const span = spans.get(candidate);
        if (span !== undefined) seam = rtl ? span.left : span.right;
    }
    return seam;
};

const planPagePaneWindows = (transition: PagePaneTransition, areas: ReadonlyMap<HTMLElement, PagePaneSpan>, bounds: GeometryBox, rtl: boolean): Map<HTMLElement, PagePaneWindowPlan> => {
    const { container } = transition;
    const plans = new Map<HTMLElement, PagePaneWindowPlan>();
    const origins = new Map(Array.from(transition.before, ([root, box]) => [root, toPagePaneSpan(box)]));
    for (const [root, target] of areas) {
        const origin = origins.get(root);
        if (origin !== undefined) {
            plans.set(root, { origin, target, anchor: rtl ? 'right' : 'left' });
            continue;
        }
        const seam = resolvePagePaneSeam(container, root, origins, transition.bounds, rtl);
        plans.set(root, { origin: collapsePagePaneSpan(seam), target, anchor: resolvePagePaneAnchor(seam, target) });
    }
    for (const root of transition.exiting) {
        const origin = origins.get(root);
        if (origin === undefined) continue;
        const seam = resolvePagePaneSeam(container, root, areas, bounds, rtl);
        plans.set(root, { origin, target: collapsePagePaneSpan(seam), anchor: resolvePagePaneAnchor(seam, origin) });
    }
    return plans;
};

const listPagePaneLayer = (elements: Iterable<Element>): HTMLElement[] => Array.from(elements).filter((element): element is HTMLElement => element instanceof HTMLElement);

const readPagePaneTiming = (container: HTMLElement): KeyframeAnimationOptions => ({
    duration: readPagePaneDuration(container, '--motion-pane-reflow-duration'),
    easing: readPagePaneToken(container, '--motion-pane-ease') || 'ease-out',
    endDelay: readPagePaneDuration(container, '--motion-pane-settle-duration'),
    fill: 'both'
});

const animatePagePaneLayers = (transition: PagePaneTransition, timing: KeyframeAnimationOptions): void => {
    const animated = new Set(transition.choreography.map((animation) => (animation.effect instanceof KeyframeEffect && animation.effect.getKeyframes().some((frame) => 'translate' in frame) ? animation.effect.target : null)));
    for (const [root, motion] of transition.layers) {
        const frames = listPagePaneLayer(root.children);
        const layers: Array<readonly [readonly HTMLElement[], readonly [number, number]]> = [
            [[root], motion.root],
            [frames, motion.frame],
            [frames.flatMap((frame) => listPagePaneLayer(frame.children)), motion.content]
        ];
        for (const [elements, [first, last]] of layers) {
            for (const element of elements) {
                const lift = elements === frames && element.classList.contains(PAGE_PANE_OUTLET_CLASS) ? motion.lift : 0;
                if (animated.has(element) || [first, last, lift].every((value) => Math.abs(value) <= PAGE_PANE_LAYOUT_TOLERANCE_PX)) continue;
                const animation = element.animate([{ translate: `${String(first)}px ${String(lift)}px` }, { translate: `${String(last)}px 0` }], timing);
                animation.pause();
                transition.choreography.push(animation);
            }
        }
    }
};

const stagePagePaneItems = (transition: PagePaneTransition, laidOut: readonly HTMLElement[], timing: KeyframeAnimationOptions): void => {
    const targets = new Map<HTMLElement, PagePaneItemPositions>();
    for (const root of laidOut) {
        const origin = transition.items.get(root);
        if (origin !== undefined && origin.size > 0) targets.set(root, measurePagePaneItems(root, origin.keys()));
    }
    const shrinking = new Set<HTMLElement>();
    for (const root of laidOut) {
        const before = transition.before.get(root);
        const after = transition.after.get(root);
        if (before === undefined || after === undefined || before.width <= after.width + PAGE_PANE_LAYOUT_TOLERANCE_PX) continue;
        holdPagePane(transition, root, before, 'roomy', before.width - after.width);
        shrinking.add(root);
    }
    if (shrinking.size > 0) {
        dispatchPaneRelayout(transition.container.ownerDocument.defaultView);
        transition.after = measurePagePaneBoxes(laidOut, isPagePaneLaidOut);
    }
    transition.choreography.push(...animatePagePaneGhosts(transition, targets, timing));
    for (const [root, target] of targets) {
        const origin = transition.items.get(root);
        if (origin !== undefined) transition.choreography.push(...animatePagePaneItems(origin, shrinking.has(root) ? measurePagePaneItems(root, target.keys()) : target, target, timing));
    }
};

const stagePagePaneMotion = (transition: PagePaneTransition, roots: readonly HTMLElement[]): void => {
    const { container } = transition;
    const rtl = isRtl(container);
    const timing = readPagePaneTiming(container);
    for (const [root, box] of transition.before) {
        if (root.isConnected && (!isPagePaneLaidOut(root) || root === transition.closing)) {
            transition.exiting.add(root);
            holdPagePane(transition, root, box, 'shown');
        }
    }
    const laidOut = listPagePaneRoots(container).filter((root) => roots.includes(root) && !transition.exiting.has(root) && isPagePaneLaidOut(root));
    for (const root of laidOut) holdPagePane(transition, root, null, 'sized');
    applyPagePaneSplit(container, transition.exiting);
    dispatchPaneRelayout(container.ownerDocument.defaultView);
    transition.after = measurePagePaneBoxes(laidOut, isPagePaneLaidOut);
    stagePagePaneItems(transition, laidOut, timing);
    const areas = resolvePagePaneAreas(container, transition.after, rtl);
    if (areas === null) return;
    const bounds = measureLayoutBox(container);
    const boxes = new Map([...transition.after, ...measurePagePaneBoxes(transition.exiting, isPagePaneDisplayed)]);
    const lifts = measurePagePaneOutletOffsets(transition.after);
    for (const [root, plan] of planPagePaneWindows(transition, areas, bounds, rtl)) {
        const box = boxes.get(root);
        const after = lifts.get(root);
        const lift = after === undefined ? 0 : (transition.outlets.get(root) ?? after) - after;
        const motion = box === undefined ? null : resolvePagePaneLayerMotion(box, plan.origin, plan.target, plan.anchor, bounds, rtl, lift);
        if (motion !== null) transition.layers.set(root, motion);
    }
    animatePagePaneLayers(transition, timing);
};

const isPagePaneAwaitingContent = (transition: PagePaneTransition, root: HTMLElement): boolean => !transition.before.has(root) && root.isConnected && !root.hidden && dom.resolve(PAGE_PANE_READY_SELECTOR, root) === null;

const failPagePaneMotion = (transition: PagePaneTransition, error: Error): void => {
    if (transitions.get(transition.container) !== transition) return;
    endPagePaneTransition(transition, false);
    if (!isAbortError(error)) errorHandler.error('PagePaneMotion', 'Pane transition failed', ensureError(error));
};

const playPagePaneAnimations = (transition: PagePaneTransition): void => {
    animatePagePaneLayers(transition, readPagePaneTiming(transition.container));
    alignEnteringPages(transition);
    for (const animation of transition.choreography) {
        if (animation.playState === 'paused') animation.play();
    }
    transition.choreography.push(...transition.deferred.splice(0).map((create) => create()));
    void Promise.all(transition.choreography.map((animation) => animation.finished))
        .then(() => {
            if (transitions.get(transition.container) === transition) endPagePaneTransition(transition);
        })
        .catch((error: Error) => failPagePaneMotion(transition, error));
};

const releasePagePaneEntrances = (transition: PagePaneTransition, waiting: Set<HTMLElement>): void => {
    const release = (): void => {
        for (const root of waiting) {
            if (!isPagePaneAwaitingContent(transition, root)) waiting.delete(root);
        }
        if (waiting.size > 0 || transitions.get(transition.container) !== transition) return;
        transition.readiness?.disconnect();
        transition.readiness = null;
        if (transition.deadline !== null) transition.resources.clearTimeout(transition.deadline);
        transition.deadline = null;
        void awaitPagePaneCalm(transition)
            .then(() => {
                if (transitions.get(transition.container) === transition) playPagePaneAnimations(transition);
            })
            .catch((error) => failPagePaneMotion(transition, ensureError(error)));
    };
    transition.readiness = new MutationObserver(release);
    for (const root of waiting) transition.readiness.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });
    transition.deadline = transition.resources.setTimeout(
        () => {
            waiting.clear();
            release();
        },
        readPagePaneDuration(transition.container, '--motion-pane-ready-timeout')
    );
    release();
};

const choreographPagePanes = (transition: PagePaneTransition, roots: readonly HTMLElement[]): void => {
    const { container } = transition;
    const view = container.ownerDocument.defaultView;
    transition.resources.addEventListener(container.ownerDocument, 'visibilitychange', () => {
        if (container.ownerDocument.visibilityState === 'hidden') endPagePaneTransition(transition);
    });
    const abortTransition = (): void => endPagePaneTransition(transition, false);
    transition.resources.addEventListener(transition.controller.signal, 'abort', abortTransition, { once: true });
    const visualDeadline = readPagePaneDuration(container, '--motion-pane-ready-timeout') + 2 * PAGE_PANE_CALM_LIMIT_MS + readPagePaneDuration(container, '--motion-pane-reflow-duration') + readPagePaneDuration(container, '--motion-pane-settle-duration');
    transition.resources.setTimeout(() => endPagePaneTransition(transition), visualDeadline);
    stagePagePaneMotion(transition, roots);
    for (const animation of transition.choreography) void animation.finished.catch((error) => failPagePaneMotion(transition, ensureError(error)));
    if (view === null || transition.choreography.length === 0) {
        endPagePaneTransition(transition);
        return;
    }
    const waiting = new Set(Array.from(transition.after.keys()).filter((root) => isPagePaneAwaitingContent(transition, root)));
    transition.phase = 'animating';
    void awaitPagePaneCalm(transition)
        .then(() => {
            if (transitions.get(container) !== transition) return;
            if (waiting.size > 0) releasePagePaneEntrances(transition, waiting);
            else playPagePaneAnimations(transition);
        })
        .catch((error: Error) => failPagePaneMotion(transition, error));
};

export { choreographPagePanes };
