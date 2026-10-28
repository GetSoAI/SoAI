/* SoAI - Shared main timeline observation and animation-frame coordination [frontend/assets/ts/features/chat/mainTimelineCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMainTimelineKeyboardScrollEvent } from '@features/chat/mainTimelineScroll.ts';

type TimelineFrameWrite = () => void;
type TimelineFrameMeasure = () => TimelineFrameWrite | null;
type TimelineResizeListener = (entries: readonly ResizeObserverEntry[]) => void;
type TimelineMutationListener = (records: readonly MutationRecord[]) => void;
type NativeGesturePhase = 'idle' | 'touching' | 'settling';

type MainTimelineCoordinator = {
    scheduleFrame: (key: string, measure: TimelineFrameMeasure) => void;
    cancelFrame: (key: string) => void;
    observeResize: (element: Element) => () => void;
    subscribeResize: (listener: TimelineResizeListener) => () => void;
    subscribeMutations: (listener: TimelineMutationListener) => () => void;
    subscribeNativeGestureSettled: (listener: () => void) => () => void;
    getCachedElementHeight: (element: Element) => number | null;
    isNativeGestureActive: () => boolean;
    release: () => void;
};

type MainTimelineCoordinatorState = {
    coordinator: MainTimelineCoordinator;
    messagesRoot: HTMLElement;
    retain: () => void;
};

const NATIVE_GESTURE_SETTLE_DELAY_MS = 100;
const coordinatorByArea = new WeakMap<HTMLElement, MainTimelineCoordinatorState>();

const createMainTimelineCoordinatorState = (messagesArea: HTMLElement, messagesRoot: HTMLElement, windowRef: Window & typeof globalThis): MainTimelineCoordinatorState => {
    const resizeListeners = new Set<TimelineResizeListener>();
    const mutationListeners = new Set<TimelineMutationListener>();
    const nativeGestureSettledListeners = new Set<() => void>();
    const resizeObservationCounts = new Map<Element, number>();
    const cachedHeightByElement = new WeakMap<Element, number>();
    const pendingFrameMeasures = new Map<string, TimelineFrameMeasure>();
    let referenceCount = 0;
    let frameId: number | null = null;
    let nativeGestureSettleTimerId: number | null = null;
    let nativeGesturePhase: NativeGesturePhase = 'idle';
    let disposed = false;

    const ResizeObserverCtor = windowRef.ResizeObserver;
    const MutationObserverCtor = windowRef.MutationObserver;
    const TouchEventCtor = windowRef.TouchEvent;
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
            frameId = windowRef.requestAnimationFrame(flushFrame);
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
            frameId = windowRef.requestAnimationFrame(flushFrame);
        }
    };
    const cancelFrame = (key: string): void => {
        pendingFrameMeasures.delete(key);
        if (pendingFrameMeasures.size === 0 && frameId !== null) {
            windowRef.cancelAnimationFrame(frameId);
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

    const scheduleNativeGestureSettled = (): void => {
        if (nativeGestureSettleTimerId !== null) {
            windowRef.clearTimeout(nativeGestureSettleTimerId);
        }
        nativeGestureSettleTimerId = windowRef.setTimeout(() => {
            nativeGestureSettleTimerId = null;
            nativeGesturePhase = 'idle';
            for (const listener of nativeGestureSettledListeners) {
                listener();
            }
        }, NATIVE_GESTURE_SETTLE_DELAY_MS);
    };
    const handleTouchStart = (): void => {
        nativeGesturePhase = 'touching';
        if (nativeGestureSettleTimerId !== null) {
            windowRef.clearTimeout(nativeGestureSettleTimerId);
            nativeGestureSettleTimerId = null;
        }
    };
    const handleTouchEnd = (event: Event): void => {
        if (typeof TouchEventCtor === 'function' && event instanceof TouchEventCtor && Array.from(event.touches).some((contact) => contact.target instanceof windowRef.Node && messagesArea.contains(contact.target))) return;
        nativeGesturePhase = 'settling';
        scheduleNativeGestureSettled();
    };
    const handleScroll = (): void => {
        if (nativeGesturePhase === 'settling') {
            scheduleNativeGestureSettled();
        }
    };
    const handleWheel = (): void => {
        if (nativeGesturePhase === 'touching') return;
        nativeGesturePhase = 'settling';
        scheduleNativeGestureSettled();
    };
    const handleKeyboardScroll = (event: Event): void => {
        const target = event.target;
        if (isMainTimelineKeyboardScrollEvent(event) && !event.defaultPrevented && (target === messagesArea.ownerDocument.body || (target instanceof Node && messagesArea.contains(target)))) handleWheel();
    };
    messagesArea.ownerDocument.addEventListener('keydown', handleKeyboardScroll, { passive: true });
    messagesArea.addEventListener('wheel', handleWheel, { passive: true });
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
        nativeGestureSettledListeners.clear();
        resizeObservationCounts.clear();
        pendingFrameMeasures.clear();
        messagesArea.ownerDocument.removeEventListener('keydown', handleKeyboardScroll);
        messagesArea.removeEventListener('wheel', handleWheel);
        messagesArea.removeEventListener('touchstart', handleTouchStart);
        messagesArea.removeEventListener('touchend', handleTouchEnd);
        messagesArea.removeEventListener('touchcancel', handleTouchEnd);
        messagesArea.removeEventListener('scroll', handleScroll);
        if (frameId !== null) {
            windowRef.cancelAnimationFrame(frameId);
            frameId = null;
        }
        if (nativeGestureSettleTimerId !== null) {
            windowRef.clearTimeout(nativeGestureSettleTimerId);
            nativeGestureSettleTimerId = null;
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
        subscribeNativeGestureSettled: (listener) => subscribe(nativeGestureSettledListeners, listener),
        getCachedElementHeight: (element) => cachedHeightByElement.get(element) ?? null,
        isNativeGestureActive: () => nativeGesturePhase !== 'idle',
        release
    };
    return { coordinator, messagesRoot, retain };
};

const acquireMainTimelineCoordinator = (messagesArea: HTMLElement, messagesRoot: HTMLElement): MainTimelineCoordinator => {
    const windowRef = messagesArea.ownerDocument.defaultView;
    if (!windowRef || typeof windowRef.ResizeObserver !== 'function' || typeof windowRef.MutationObserver !== 'function') {
        throw new Error('ResizeObserver and MutationObserver are required for main timeline coordination');
    }
    if (typeof windowRef.requestAnimationFrame !== 'function' || typeof windowRef.cancelAnimationFrame !== 'function') {
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
    const created = createMainTimelineCoordinatorState(messagesArea, messagesRoot, windowRef);
    coordinatorByArea.set(messagesArea, created);
    created.retain();
    return created.coordinator;
};

export { acquireMainTimelineCoordinator };
export type { MainTimelineCoordinator, TimelineFrameMeasure, TimelineFrameWrite };
