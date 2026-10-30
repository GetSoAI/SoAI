/* SoAI - Cancellable element scrolling with settled completion [frontend/assets/ts/core/animations/scrollMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';
import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { scrollElementTo } from '@core/scroll.ts';

const animateElementScroll = async (element: HTMLElement, destination: Pick<ScrollToOptions, 'left' | 'top'>, signal: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const view = element.ownerDocument.defaultView;
    if (!view) throw new Error('Timeline scrolling requires a document window');
    const atDestination = (): boolean => (destination.top === undefined || Math.abs(destination.top - element.scrollTop) < 1) && (destination.left === undefined || Math.abs(destination.left - element.scrollLeft) < 1);
    if (atDestination()) return;
    const completion = createDeferred<void>();
    let timer: number | null = null;
    let frame: number | null = null;
    let finished = false;
    const finish = (cancelled: boolean): void => {
        if (finished) return;
        finished = true;
        element.removeEventListener('scrollend', settled);
        element.removeEventListener('scroll', scheduleSettled);
        signal.removeEventListener('abort', cancel);
        if (timer !== null) view.clearTimeout(timer);
        if (frame !== null) view.cancelAnimationFrame(frame);
        if (cancelled) {
            scrollElementTo(element, { ...(destination.top === undefined ? {} : { top: element.scrollTop }), ...(destination.left === undefined ? {} : { left: element.scrollLeft }), behavior: 'instant' });
            completion.reject(createAbortError());
        } else completion.resolve();
    };
    const settled = (): void => {
        if (atDestination()) finish(false);
    };
    const cancel = (): void => finish(true);
    const scheduleSettled = (): void => {
        if (timer !== null) view.clearTimeout(timer);
        timer = view.setTimeout(() => finish(false), 150);
    };
    signal.addEventListener('abort', cancel, { once: true });
    if (prefersReducedMotion(element)) {
        scrollElementTo(element, { ...destination, behavior: 'instant' });
        frame = view.requestAnimationFrame(() => finish(false));
    } else {
        element.addEventListener('scrollend', settled);
        element.addEventListener('scroll', scheduleSettled, { passive: true });
        scheduleSettled();
        scrollElementTo(element, { ...destination, behavior: 'smooth' });
    }
    await completion.promise;
};

export { animateElementScroll };
