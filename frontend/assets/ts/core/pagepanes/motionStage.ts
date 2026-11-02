/* SoAI - Pane workspace motion state, geometry and layout holds [frontend/assets/ts/core/pagepanes/motionStage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { dispatchPaneRelayout } from '@core/layout/paneRelayout.ts';
import { measurePagePaneItemOrigin, resolvePagePaneSection, type PagePaneItemPositions } from '@core/pagepanes/motionContent.ts';
import type { PagePaneLayerMotion } from '@core/pagepanes/motionWindows.ts';

type PagePaneTransitionPhase = 'frozen' | 'animating';
type PagePaneHeldState = 'shown' | 'sized' | 'roomy' | 'gone';

interface PagePaneGhostLayer {
    readonly element: HTMLElement;
    readonly root: HTMLElement;
    readonly left: number;
    readonly top: number;
    readonly ghosts: Map<HTMLElement, HTMLElement>;
}

interface PagePaneTransition {
    readonly container: HTMLElement;
    readonly bounds: GeometryBox;
    readonly before: ReadonlyMap<HTMLElement, GeometryBox>;
    readonly outlets: ReadonlyMap<HTMLElement, number>;
    readonly items: ReadonlyMap<HTMLElement, PagePaneItemPositions>;
    after: ReadonlyMap<HTMLElement, GeometryBox>;
    readonly holds: Set<HTMLElement>;
    readonly choreography: Animation[];
    readonly deferred: Array<() => Animation>;
    readonly exiting: Set<HTMLElement>;
    readonly layers: Map<HTMLElement, PagePaneLayerMotion>;
    readonly ghostLayers: PagePaneGhostLayer[];
    readonly closing: HTMLElement | null;
    readonly settled: Set<(completed: boolean) => void>;
    readonly controller: AbortController;
    readonly resources: ResourceTracker;
    readonly previousSplit: boolean | undefined;
    finished: boolean;
    phase: PagePaneTransitionPhase;
    readiness: MutationObserver | null;
    deadline: number | null;
}

const PAGE_PANE_CHROME_ATTRIBUTE = 'data-pane-chrome';
const PAGE_PANE_SPLIT_ATTRIBUTE = 'data-pane-split';
const PAGE_PANE_HELD_ATTRIBUTE = 'data-pane-held';
const PAGE_PANE_RESERVE_ATTRIBUTE = 'data-pane-reserve';
const PAGE_PANE_RESTORING_ATTRIBUTE = 'data-pane-restoring';
const PAGE_PANE_LAYOUT_TOLERANCE_PX = 0.5;

const transitions = new WeakMap<HTMLElement, PagePaneTransition>();
const splitTargets = new WeakMap<HTMLElement, boolean>();

const isPagePanePresent = (root: HTMLElement): boolean => !root.hidden && root.getAttribute(PAGE_PANE_HELD_ATTRIBUTE) !== 'gone';

const listPagePaneRoots = (container: HTMLElement): HTMLElement[] => Array.from(container.children).filter((child): child is HTMLElement => child instanceof HTMLElement && child.classList.contains('page-pane'));

const applyPagePaneSplit = (container: HTMLElement, deferred: ReadonlySet<HTMLElement> | null = null): void => {
    const reserved = container.hasAttribute(PAGE_PANE_RESERVE_ATTRIBUTE);
    if (!splitTargets.has(container) && !reserved) return;
    const split = reserved || (splitTargets.get(container) === true && listPagePaneRoots(container).filter(isPagePanePresent).length > 1);
    if (container.getAttribute(PAGE_PANE_SPLIT_ATTRIBUTE) !== String(split)) container.setAttribute(PAGE_PANE_SPLIT_ATTRIBUTE, String(split));
    for (const root of listPagePaneRoots(container)) {
        const chrome = String(split && !root.hidden);
        if (!deferred?.has(root) && root.getAttribute(PAGE_PANE_CHROME_ATTRIBUTE) !== chrome) root.setAttribute(PAGE_PANE_CHROME_ATTRIBUTE, chrome);
    }
};

const readPagePaneToken = (container: HTMLElement, property: string): string => getComputedStyleStrict(container.ownerDocument.documentElement).getPropertyValue(property).trim();

const readPagePaneDuration = (container: HTMLElement, property: string): number => parseMaxCssDurationMs(readPagePaneToken(container, property));

const isPagePaneDisplayed = (root: HTMLElement): boolean => {
    if (!root.isConnected) return false;
    const style = getComputedStyleStrict(root);
    return style.display !== 'none' && style.visibility !== 'hidden';
};

const isPagePaneLaidOut = (root: HTMLElement): boolean => root.isConnected && !root.hidden;

const measurePagePaneBoxes = (roots: Iterable<HTMLElement>, include: (root: HTMLElement) => boolean): Map<HTMLElement, GeometryBox> => {
    const boxes = new Map<HTMLElement, GeometryBox>();
    for (const root of roots) {
        if (!include(root)) continue;
        const box = measureLayoutBox(root);
        if (box.width > 0 && box.height > 0) boxes.set(root, box);
    }
    return boxes;
};

const PAGE_PANE_OUTLET_CLASS = 'page-pane-outlet';

const measurePagePaneOutletOffsets = (boxes: ReadonlyMap<HTMLElement, GeometryBox>): Map<HTMLElement, number> => {
    const offsets = new Map<HTMLElement, number>();
    for (const [root, box] of boxes) {
        const section = resolvePagePaneSection(root);
        if (section !== null) offsets.set(root, measurePagePaneItemOrigin(section).top - box.top);
    }
    return offsets;
};

const isSamePagePaneLayout = (before: ReadonlyMap<HTMLElement, GeometryBox>, after: ReadonlyMap<HTMLElement, GeometryBox>): boolean => {
    if (before.size !== after.size) return false;
    for (const [root, box] of after) {
        const previous = before.get(root);
        if (previous === undefined || Math.abs(previous.left - box.left) > PAGE_PANE_LAYOUT_TOLERANCE_PX || Math.abs(previous.width - box.width) > PAGE_PANE_LAYOUT_TOLERANCE_PX) return false;
    }
    return true;
};

const PAGE_PANE_HELD_PROPERTIES = ['--page-pane-held-left', '--page-pane-held-top', '--page-pane-held-width', '--page-pane-held-height', '--page-pane-held-room', '--page-pane-held-section-padding'];

const holdPagePane = (transition: PagePaneTransition, root: HTMLElement, box: GeometryBox | null, state: PagePaneHeldState, room = 0): void => {
    const section = room > 0 ? resolvePagePaneSection(root) : null;
    const padding = section === null ? 0 : Number.parseFloat(getComputedStyleStrict(section).paddingInlineEnd);
    const values = box === null ? [0, 0, 0, 0] : [box.left - transition.bounds.left, box.top - transition.bounds.top, box.width, box.height];
    dom.setStyles(root, Object.fromEntries(PAGE_PANE_HELD_PROPERTIES.map((property, index) => [property, `${String([...values, room, padding + room][index])}px`])));
    root.setAttribute(PAGE_PANE_HELD_ATTRIBUTE, state);
    transition.holds.add(root);
};

const releasePagePaneHolds = (transition: PagePaneTransition): void => {
    const failures: Error[] = [];
    for (const root of transition.holds) {
        runCleanupStepCollectingFailure(() => dom.setStyles(root, Object.fromEntries(PAGE_PANE_HELD_PROPERTIES.map((property) => [property, null]))), failures);
        runCleanupStepCollectingFailure(() => {
            if (root.getAttribute(PAGE_PANE_HELD_ATTRIBUTE) !== 'gone') root.removeAttribute(PAGE_PANE_HELD_ATTRIBUTE);
        }, failures);
    }
    transition.holds.clear();
    throwCollectedCleanupFailures(failures);
};

const endPagePaneTransition = (transition: PagePaneTransition, completed = true): void => {
    if (transition.finished) return;
    transition.finished = true;
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => transition.controller.abort(), failures);
    void transition.resources.dispose().catch((error) => errorHandler.warn('PagePaneMotion', 'Motion resource cleanup failed', ensureError(error)));
    runCleanupStepCollectingFailure(() => transition.readiness?.disconnect(), failures);
    transition.readiness = null;
    if (transition.deadline !== null) transition.resources.clearTimeout(transition.deadline);
    transition.deadline = null;
    for (const animation of transition.choreography.splice(0)) runCleanupStepCollectingFailure(() => animation.cancel(), failures);
    transition.deferred.length = 0;
    if (completed && transition.closing !== null && !transition.closing.hidden) transition.closing.setAttribute(PAGE_PANE_HELD_ATTRIBUTE, 'gone');
    if (!completed && transition.closing !== null) {
        transition.closing.removeAttribute(PAGE_PANE_HELD_ATTRIBUTE);
        if (transition.previousSplit === undefined) splitTargets.delete(transition.container);
        else splitTargets.set(transition.container, transition.previousSplit);
    }
    const resized = transition.holds.size > 0;
    runCleanupStepCollectingFailure(() => releasePagePaneHolds(transition), failures);
    if (resized) runCleanupStepCollectingFailure(() => dispatchPaneRelayout(transition.container.ownerDocument.defaultView), failures);
    transition.exiting.clear();
    transition.layers.clear();
    for (const layer of transition.ghostLayers.splice(0)) runCleanupStepCollectingFailure(() => layer.element.remove(), failures);
    if (transitions.get(transition.container) === transition) transitions.delete(transition.container);
    if (!transitions.has(transition.container)) runCleanupStepCollectingFailure(() => applyPagePaneSplit(transition.container), failures);
    for (const settled of [...transition.settled]) runCleanupStepCollectingFailure(() => settled(completed && failures.length === 0), failures);
    transition.settled.clear();
    throwCollectedCleanupFailures(failures);
};

export { PAGE_PANE_HELD_ATTRIBUTE, PAGE_PANE_LAYOUT_TOLERANCE_PX, PAGE_PANE_RESERVE_ATTRIBUTE, PAGE_PANE_RESTORING_ATTRIBUTE, PAGE_PANE_OUTLET_CLASS, applyPagePaneSplit, endPagePaneTransition, holdPagePane, isPagePaneDisplayed, isPagePaneLaidOut, isPagePanePresent, isSamePagePaneLayout, listPagePaneRoots, measurePagePaneBoxes, measurePagePaneOutletOffsets, readPagePaneDuration, readPagePaneToken, releasePagePaneHolds, splitTargets, transitions };
export type { PagePaneGhostLayer, PagePaneTransition };
