/* SoAI - Chat feature main timeline scroll [frontend/assets/ts/features/chat/mainTimelineScroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SCROLL_BOTTOM_THRESHOLD } from '@features/chat/chatConstants.ts';

const MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE = 'data-auto-scroll-lock';
const programmaticScrollOffsets = new WeakMap<HTMLElement, number>();

type MainTimelineScrollMeasurement = {
    clientHeight: number;
    scrollHeight: number;
    scrollTop: number;
};

const measureMainTimelineScroll = (element: HTMLElement): MainTimelineScrollMeasurement => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    scrollTop: element.scrollTop
});

const isMainTimelineMeasurementAtBottom = (measurement: MainTimelineScrollMeasurement): boolean => measurement.scrollHeight - measurement.scrollTop - measurement.clientHeight <= CHAT_SCROLL_BOTTOM_THRESHOLD;

const isMainTimelineAtBottom = (element: HTMLElement): boolean => isMainTimelineMeasurementAtBottom(measureMainTimelineScroll(element));

const isMainTimelineAutoScrollLocked = (element: HTMLElement): boolean => element.getAttribute(MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE) === 'true';

const writeMainTimelineScrollTop = (element: HTMLElement, top: number): void => {
    const previousTop = element.scrollTop;
    if (top === previousTop) return;
    element.scrollTop = top;
    const appliedOffset = element.scrollTop - previousTop;
    if (appliedOffset !== 0) programmaticScrollOffsets.set(element, (programmaticScrollOffsets.get(element) ?? 0) + appliedOffset);
};

const consumeMainTimelineProgrammaticScrollOffset = (element: HTMLElement): number => {
    const offset = programmaticScrollOffsets.get(element) ?? 0;
    programmaticScrollOffsets.delete(element);
    return offset;
};

export { MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE, consumeMainTimelineProgrammaticScrollOffset, isMainTimelineAtBottom, isMainTimelineAutoScrollLocked, isMainTimelineMeasurementAtBottom, measureMainTimelineScroll, writeMainTimelineScrollTop };
export type { MainTimelineScrollMeasurement };
