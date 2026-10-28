/* SoAI - Shared single-pass FLIP reorder motion for keyed rows and cards inside a visible band [frontend/assets/ts/core/animations/reorderMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureLayoutBox, measureLayoutViewport, type GeometryBox } from '@core/layout/elementGeometry.ts';

type ReorderMotionKey = string | HTMLElement;
type ReorderMotionEdge = 'start' | 'end';

interface ReorderMotion {
    play(nextContainer?: HTMLElement): void;
}

interface ReorderMotionBand {
    top: number;
    bottom: number;
}

interface ReorderMotionTarget {
    key: ReorderMotionKey;
    target: HTMLElement;
    box: GeometryBox;
    visible: boolean;
}

interface ReorderMotionOrderRange {
    first: number;
    last: number;
}

interface ReorderMotionSnapshot {
    band: ReorderMotionBand;
    targets: ReadonlyMap<ReorderMotionKey, ReorderMotionTarget>;
    previousOrder: ReadonlyMap<string, number>;
    visibleOrderRange: ReorderMotionOrderRange | null;
}

const REORDER_MOTION_DURATION_PROPERTY = '--reorder-motion-duration';
const REORDER_MOTION_EASE_PROPERTY = '--reorder-motion-ease';
const REORDER_MOTION_EXIT_DURATION_PROPERTY = '--reorder-motion-exit-duration';
const REORDER_MOTION_EXIT_SCALE_PROPERTY = '--reorder-motion-exit-scale';
const REORDER_MOTION_FALLBACK_EASE = 'ease-out';
const REORDER_MOTION_THRESHOLD_PX = 0.5;
const REORDER_MOTION_OCCURRENCE_SEPARATOR = '\u0000';
const INACTIVE_REORDER_MOTION: ReorderMotion = Object.freeze({ play: (): void => {} });

const runningReorderAnimations = new WeakMap<HTMLElement, readonly Animation[]>();
const runningExitAnimations = new WeakMap<HTMLElement, readonly Animation[]>();

const resolveLeadingCellTextKey = (element: HTMLElement): string | null => {
    if (!(element instanceof HTMLTableRowElement)) return null;
    return element.cells[0]?.textContent?.trim() || null;
};

const collectReorderMotionTargets = (container: HTMLElement, targetSelector: string | null): HTMLElement[] => {
    if (targetSelector !== null) return dom.resolveAll(targetSelector, container).filter((target): target is HTMLElement => target instanceof HTMLElement);
    const targets: HTMLElement[] = [];
    for (const child of container.children) {
        if (!(child instanceof HTMLElement)) continue;
        if (getComputedStyleStrict(child).display !== 'contents') {
            targets.push(child);
            continue;
        }
        for (const nested of child.children) {
            if (nested instanceof HTMLElement) targets.push(nested);
        }
    }
    return targets;
};

const measureReorderMotionBand = (container: HTMLElement): ReorderMotionBand | null => {
    let top = 0;
    let bottom = measureLayoutViewport(container).height;
    const documentElement = container.ownerDocument.documentElement;
    for (let ancestor: HTMLElement | null = container; ancestor !== null && ancestor !== documentElement; ancestor = ancestor.parentElement) {
        if (getComputedStyleStrict(ancestor).overflowY === 'visible') continue;
        const box = measureLayoutBox(ancestor);
        top = Math.max(top, box.top);
        bottom = Math.min(bottom, box.bottom);
    }
    return bottom > top ? { top, bottom } : null;
};

const measureReorderMotionTargets = (container: HTMLElement, band: ReorderMotionBand, resolveKey: ((element: HTMLElement) => string | null) | null, targetSelector: string | null): Map<ReorderMotionKey, ReorderMotionTarget> => {
    const targets = new Map<ReorderMotionKey, ReorderMotionTarget>();
    const occurrences = new Map<string, number>();
    for (const target of collectReorderMotionTargets(container, targetSelector)) {
        const box = measureLayoutBox(target);
        if (box.height <= 0) continue;
        const resolvedKey = resolveKey?.(target) ?? null;
        const occurrence = resolvedKey === null ? 0 : (occurrences.get(resolvedKey) ?? 0);
        if (resolvedKey !== null) occurrences.set(resolvedKey, occurrence + 1);
        const key = resolvedKey === null ? target : occurrence === 0 ? resolvedKey : `${resolvedKey}${REORDER_MOTION_OCCURRENCE_SEPARATOR}${occurrence}`;
        targets.set(key, { key, target, box, visible: box.bottom > band.top && box.top < band.bottom });
    }
    return targets;
};

const resolveVisibleOrderRange = (targets: ReadonlyMap<ReorderMotionKey, ReorderMotionTarget>, previousOrder: ReadonlyMap<string, number>): ReorderMotionOrderRange | null => {
    let range: ReorderMotionOrderRange | null = null;
    for (const { key, visible } of targets.values()) {
        const index = visible && typeof key === 'string' ? previousOrder.get(key) : undefined;
        if (index === undefined) continue;
        range = range === null ? { first: index, last: index } : { first: Math.min(range.first, index), last: Math.max(range.last, index) };
    }
    return range;
};

const resolveEntryEdge = (snapshot: ReorderMotionSnapshot, key: ReorderMotionKey): ReorderMotionEdge | null => {
    const first = snapshot.targets.get(key);
    if (first !== undefined) return first.box.top >= snapshot.band.bottom ? 'end' : 'start';
    const index = typeof key === 'string' ? snapshot.previousOrder.get(key) : undefined;
    if (index === undefined || snapshot.visibleOrderRange === null) return null;
    if (index > snapshot.visibleOrderRange.last) return 'end';
    return index < snapshot.visibleOrderRange.first ? 'start' : null;
};

const resolveReorderMotionTiming = (container: HTMLElement): KeyframeAnimationOptions | null => {
    const style = getComputedStyleStrict(container);
    const duration = parseMaxCssDurationMs(style.getPropertyValue(REORDER_MOTION_DURATION_PROPERTY));
    if (duration <= 0) return null;
    return { duration, easing: style.getPropertyValue(REORDER_MOTION_EASE_PROPERTY).trim() || REORDER_MOTION_FALLBACK_EASE };
};

const cancelReorderMotion = (container: HTMLElement): void => {
    for (const animation of runningReorderAnimations.get(container) ?? []) animation.cancel();
    runningReorderAnimations.delete(container);
};

const animateTranslate = (target: HTMLElement, deltaX: number, deltaY: number, timing: KeyframeAnimationOptions): Animation | null => {
    if (Math.abs(deltaX) < REORDER_MOTION_THRESHOLD_PX && Math.abs(deltaY) < REORDER_MOTION_THRESHOLD_PX) return null;
    return target.animate({ translate: [`${deltaX}px ${deltaY}px`, '0px 0px'] }, timing);
};

const playReorderMotion = (container: HTMLElement, snapshot: ReorderMotionSnapshot, resolveKey: ((element: HTMLElement) => string | null) | null, targetSelector: string | null): void => {
    if (!container.isConnected) return;
    const timing = resolveReorderMotionTiming(container);
    const band = measureReorderMotionBand(container);
    if (timing === null || band === null) return;
    const animations: Animation[] = [];
    const entering: Record<ReorderMotionEdge, ReorderMotionTarget[]> = { start: [], end: [] };
    for (const last of measureReorderMotionTargets(container, band, resolveKey, targetSelector).values()) {
        if (!last.visible) continue;
        const first = snapshot.targets.get(last.key);
        if (first?.visible === true) {
            const animation = animateTranslate(last.target, first.box.left - last.box.left, first.box.top - last.box.top, timing);
            if (animation !== null) animations.push(animation);
            continue;
        }
        const edge = resolveEntryEdge(snapshot, last.key);
        if (edge === null) animations.push(last.target.animate({ opacity: [0, 1] }, timing));
        else entering[edge].push(last);
    }
    const startOffset = band.top - Math.max(...entering.start.map(({ box }) => box.bottom));
    const endOffset = band.bottom - Math.min(...entering.end.map(({ box }) => box.top));
    for (const { target } of entering.start) animations.push(target.animate({ translate: [`0px ${startOffset}px`, '0px 0px'] }, timing));
    for (const { target } of entering.end) animations.push(target.animate({ translate: [`0px ${endOffset}px`, '0px 0px'] }, timing));
    if (animations.length > 0) runningReorderAnimations.set(container, animations);
};

const playReorderExit = (container: HTMLElement, elements: readonly HTMLElement[]): Promise<void> | null => {
    if (elements.length === 0 || !container.isConnected || typeof container.animate !== 'function' || isReducedAnimationScope(container)) return null;
    const band = measureReorderMotionBand(container);
    const style = getComputedStyleStrict(container);
    const duration = parseMaxCssDurationMs(style.getPropertyValue(REORDER_MOTION_EXIT_DURATION_PROPERTY));
    if (band === null || duration <= 0) return null;
    const scale = Number.parseFloat(style.getPropertyValue(REORDER_MOTION_EXIT_SCALE_PROPERTY));
    const timing: KeyframeAnimationOptions = { duration, easing: style.getPropertyValue(REORDER_MOTION_EASE_PROPERTY).trim() || REORDER_MOTION_FALLBACK_EASE, fill: 'forwards' };
    const pending: Animation[] = [];
    for (const element of elements) {
        const running = runningExitAnimations.get(element);
        if (running !== undefined) {
            pending.push(...running);
            continue;
        }
        const targets = getComputedStyleStrict(element).display === 'contents' ? Array.from(element.children).filter((child): child is HTMLElement => child instanceof HTMLElement) : [element];
        const visibleTargets = targets.filter((target) => {
            const box = measureLayoutBox(target);
            return box.height > 0 && box.bottom > band.top && box.top < band.bottom;
        });
        if (visibleTargets.length === 0) continue;
        const animations = visibleTargets.map((target) => target.animate({ opacity: [1, 0], scale: [1, Number.isFinite(scale) ? scale : 1] }, timing));
        runningExitAnimations.set(element, animations);
        pending.push(...animations);
    }
    return pending.length === 0 ? null : Promise.allSettled(pending.map((animation) => animation.finished)).then(() => undefined);
};

const cancelReorderExit = (element: HTMLElement): void => {
    for (const animation of runningExitAnimations.get(element) ?? []) animation.cancel();
    runningExitAnimations.delete(element);
};

const captureReorderMotion = (container: HTMLElement, resolveKey: ((element: HTMLElement) => string | null) | null = null, previousOrder: readonly string[] = [], targetSelector: string | null = null): ReorderMotion => {
    if (!container.isConnected || typeof container.animate !== 'function' || isReducedAnimationScope(container)) return INACTIVE_REORDER_MOTION;
    const band = measureReorderMotionBand(container);
    if (band === null) return INACTIVE_REORDER_MOTION;
    const targets = measureReorderMotionTargets(container, band, resolveKey, targetSelector);
    const previousIndexes = new Map(previousOrder.map((key, index) => [key, index]));
    const snapshot: ReorderMotionSnapshot = { band, targets, previousOrder: previousIndexes, visibleOrderRange: resolveVisibleOrderRange(targets, previousIndexes) };
    return {
        play: (nextContainer: HTMLElement = container): void => {
            cancelReorderMotion(container);
            cancelReorderMotion(nextContainer);
            playReorderMotion(nextContainer, snapshot, resolveKey, targetSelector);
        }
    };
};

export { cancelReorderExit, captureReorderMotion, playReorderExit, resolveLeadingCellTextKey };
export type { ReorderMotion };
