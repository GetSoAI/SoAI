/* SoAI - Shared main timeline observation and animation-frame coordination [frontend/assets/ts/features/chat/mainTimelineCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type TimelineFrameWrite = () => void;
type TimelineFrameMeasure = () => TimelineFrameWrite | null;
type TimelineResizeListener = (entries: readonly ResizeObserverEntry[]) => void;
type TimelineMutationListener = (records: readonly MutationRecord[]) => void;

type MainTimelineCoordinator = {
    scheduleFrame: (key: string, measure: TimelineFrameMeasure) => void;
    cancelFrame: (key: string) => void;
    observeResize: (element: Element) => () => void;
    subscribeResize: (listener: TimelineResizeListener) => () => void;
    subscribeMutations: (listener: TimelineMutationListener) => () => void;
    subscribeTouchSettled: (listener: () => void) => () => void;
    getCachedElementHeight: (element: Element) => number | null;
    isDirectTouchActive: () => boolean;
    release: () => void;
};

type MainTimelineCoordinatorState = {
    coordinator: MainTimelineCoordinator;
    messagesRoot: HTMLElement;
    retain: () => void;
};

const TOUCH_SETTLE_DELAY_MS = 100;
const coordinatorByArea = new WeakMap<HTMLElement, MainTimelineCoordinatorState>();

const createMainTimelineCoordinatorState = (messagesArea: HTMLElement, messagesRoot: HTMLElement, win: Window & typeof globalThis): MainTimelineCoordinatorState => {
    const resizeListeners = new Set<TimelineResizeListener>();
    const mutationListeners = new Set<TimelineMutationListener>();
    const touchSettledListeners = new Set<() => void>();
    const resizeObservationCounts = new Map<Element, number>();
    const cachedHeightByElement = new WeakMap<Element, number>();
    const pendingFrameMeasures = new Map<string, TimelineFrameMeasure>();
    let referenceCount = 0;
    let frameId: number | null = null;
    let touchSettleTimerId: number | null = null;
    let directTouchActive = false;
    let disposed = false;

    const ResizeObserverCtor = win.ResizeObserver;
    const MutationObserverCtor = win.MutationObserver;
    const resizeObserver = new ResizeObserverCtor((entries: ResizeObserverEntry[]) => {
        for (const entry of entries) {
            cachedHeightByElement.set(entry.target, entry.contentRect.height);
        }
        for (const listener of resizeListeners) {
            listener(entries);
        }
    });
    const mutationObserver = new MutationObserverCtor((records: MutationRecord[]) => {
        for (const listener of mutationListeners) {
            listener(records);
        }
    });

    mutationObserver.observe(messagesRoot, {
        attributeFilter: ['class', 'data-collapsed', 'data-collapsing', 'data-stream-segment-key', 'style'],
        attributeOldValue: true,
        attributes: true,
        characterData: true,
        childList: true,
        subtree: true
    });
    mutationObserver.observe(messagesArea, {
        attributeFilter: ['class', 'style'],
        attributes: true
    });

    const flushFrame = (): void => {
        frameId = null;
        if (disposed) {
            return;
        }
        const measures = Array.from(pendingFrameMeasures.values());
        pendingFrameMeasures.clear();
        const writes: TimelineFrameWrite[] = [];
        for (const measure of measures) {
            const write = measure();
            if (write) {
                writes.push(write);
            }
        }
        for (const write of writes) {
            write();
        }
        if (pendingFrameMeasures.size > 0 && frameId === null) {
            frameId = win.requestAnimationFrame(flushFrame);
        }
    };

    const scheduleFrame = (key: string, measure: TimelineFrameMeasure): void => {
        if (disposed) {
            return;
        }
        if (key.trim().length === 0) {
            throw new Error('Main timeline frame keys must not be empty');
        }
        pendingFrameMeasures.set(key, measure);
        if (frameId === null) {
            frameId = win.requestAnimationFrame(flushFrame);
        }
    };
    const cancelFrame = (key: string): void => {
        pendingFrameMeasures.delete(key);
        if (pendingFrameMeasures.size === 0 && frameId !== null) {
            win.cancelAnimationFrame(frameId);
            frameId = null;
        }
    };

    const observeResize = (element: Element): (() => void) => {
        if (disposed) {
            throw new Error('Cannot observe a disposed main timeline coordinator');
        }
        const nextCount = (resizeObservationCounts.get(element) ?? 0) + 1;
        resizeObservationCounts.set(element, nextCount);
        if (nextCount === 1) {
            resizeObserver.observe(element);
        }
        let observing = true;
        return () => {
            if (!observing || disposed) {
                return;
            }
            observing = false;
            const currentCount = resizeObservationCounts.get(element) ?? 0;
            if (currentCount <= 1) {
                resizeObservationCounts.delete(element);
                resizeObserver.unobserve(element);
                return;
            }
            resizeObservationCounts.set(element, currentCount - 1);
        };
    };

    const scheduleTouchSettled = (): void => {
        if (touchSettleTimerId !== null) {
            win.clearTimeout(touchSettleTimerId);
        }
        touchSettleTimerId = win.setTimeout(() => {
            touchSettleTimerId = null;
            directTouchActive = false;
            for (const listener of touchSettledListeners) {
                listener();
            }
        }, TOUCH_SETTLE_DELAY_MS);
    };
    const handleTouchStart = (): void => {
        directTouchActive = true;
        if (touchSettleTimerId !== null) {
            win.clearTimeout(touchSettleTimerId);
            touchSettleTimerId = null;
        }
    };
    const handleTouchEnd = (): void => {
        scheduleTouchSettled();
    };
    const handleScroll = (): void => {
        if (directTouchActive) {
            scheduleTouchSettled();
        }
    };
    messagesArea.addEventListener('touchstart', handleTouchStart, { passive: true });
    messagesArea.addEventListener('touchend', handleTouchEnd, { passive: true });
    messagesArea.addEventListener('touchcancel', handleTouchEnd, { passive: true });
    messagesArea.addEventListener('scroll', handleScroll, { passive: true });

    const subscribe = <TListener>(listeners: Set<TListener>, listener: TListener): (() => void) => {
        if (disposed) {
            throw new Error('Cannot subscribe to a disposed main timeline coordinator');
        }
        listeners.add(listener);
        return () => {
            listeners.delete(listener);
        };
    };

    const dispose = (): void => {
        if (disposed) {
            return;
        }
        disposed = true;
        coordinatorByArea.delete(messagesArea);
        mutationObserver.disconnect();
        resizeObserver.disconnect();
        resizeListeners.clear();
        mutationListeners.clear();
        touchSettledListeners.clear();
        resizeObservationCounts.clear();
        pendingFrameMeasures.clear();
        messagesArea.removeEventListener('touchstart', handleTouchStart);
        messagesArea.removeEventListener('touchend', handleTouchEnd);
        messagesArea.removeEventListener('touchcancel', handleTouchEnd);
        messagesArea.removeEventListener('scroll', handleScroll);
        if (frameId !== null) {
            win.cancelAnimationFrame(frameId);
            frameId = null;
        }
        if (touchSettleTimerId !== null) {
            win.clearTimeout(touchSettleTimerId);
            touchSettleTimerId = null;
        }
    };

    const retain = (): void => {
        if (disposed) {
            throw new Error('Cannot retain a disposed main timeline coordinator');
        }
        referenceCount += 1;
    };
    const release = (): void => {
        if (referenceCount === 0) {
            return;
        }
        referenceCount -= 1;
        if (referenceCount === 0) {
            dispose();
        }
    };
    const coordinator: MainTimelineCoordinator = {
        scheduleFrame,
        cancelFrame,
        observeResize,
        subscribeResize: (listener) => subscribe(resizeListeners, listener),
        subscribeMutations: (listener) => subscribe(mutationListeners, listener),
        subscribeTouchSettled: (listener) => subscribe(touchSettledListeners, listener),
        getCachedElementHeight: (element) => cachedHeightByElement.get(element) ?? null,
        isDirectTouchActive: () => directTouchActive,
        release
    };
    return { coordinator, messagesRoot, retain };
};

const acquireMainTimelineCoordinator = (messagesArea: HTMLElement, messagesRoot: HTMLElement): MainTimelineCoordinator => {
    const win = messagesArea.ownerDocument.defaultView;
    if (!win || typeof win.ResizeObserver !== 'function' || typeof win.MutationObserver !== 'function') {
        throw new Error('ResizeObserver and MutationObserver are required for main timeline coordination');
    }
    if (typeof win.requestAnimationFrame !== 'function' || typeof win.cancelAnimationFrame !== 'function') {
        throw new Error('requestAnimationFrame is required for main timeline coordination');
    }
    const existing = coordinatorByArea.get(messagesArea) ?? null;
    if (existing) {
        if (existing.messagesRoot !== messagesRoot) {
            throw new Error('Main timeline coordinator root cannot change while retained');
        }
        existing.retain();
        return existing.coordinator;
    }
    const created = createMainTimelineCoordinatorState(messagesArea, messagesRoot, win);
    coordinatorByArea.set(messagesArea, created);
    created.retain();
    return created.coordinator;
};

export { acquireMainTimelineCoordinator };
export type { MainTimelineCoordinator, TimelineFrameMeasure, TimelineFrameWrite };
