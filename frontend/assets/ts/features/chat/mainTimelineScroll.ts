/* SoAI - Chat feature main timeline scroll [frontend/assets/ts/features/chat/mainTimelineScroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNamedFormField } from '@core/dom/formFields.ts';
import { CHAT_SCROLL_BOTTOM_THRESHOLD } from '@features/chat/chatConstants.ts';

const USER_SCROLL_KEYS: ReadonlySet<string> = new Set(['ArrowDown', 'ArrowUp', 'End', 'Home', 'PageDown', 'PageUp', ' ']);

const isEditableKeyTarget = (target: EventTarget | null): boolean => target instanceof Element && (isNamedFormField(target) || target.closest('[contenteditable]') !== null);

const isMainTimelineKeyboardScrollEvent = (event: Event): event is KeyboardEvent => event instanceof KeyboardEvent && USER_SCROLL_KEYS.has(event.key) && !isEditableKeyTarget(event.target);

const MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE = 'data-auto-scroll-lock';
const programmaticScrollOffsets = new WeakMap<HTMLElement, number>();
const programmaticScrollOwners = new WeakMap<HTMLElement, Set<symbol>>();

const beginMainTimelineProgrammaticScroll = (element: HTMLElement): (() => void) => {
    const owners = programmaticScrollOwners.get(element) ?? new Set<symbol>();
    const owner = Symbol();
    owners.add(owner);
    programmaticScrollOwners.set(element, owners);
    return () => {
        owners.delete(owner);
        if (owners.size === 0 && programmaticScrollOwners.get(element) === owners) programmaticScrollOwners.delete(element);
    };
};

const isMainTimelineProgrammaticScrollActive = (element: HTMLElement): boolean => (programmaticScrollOwners.get(element)?.size ?? 0) > 0;

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

const isMainTimelineScrollRestoring = (element: HTMLElement): boolean => element.getAttribute(MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE) === 'restoring';

const recordMainTimelineProgrammaticScrollOffset = (element: HTMLElement, previousTop: number): void => {
    const appliedOffset = element.scrollTop - previousTop;
    if (appliedOffset !== 0) programmaticScrollOffsets.set(element, (programmaticScrollOffsets.get(element) ?? 0) + appliedOffset);
};

const writeMainTimelineScrollTop = (element: HTMLElement, top: number): void => {
    const previousTop = element.scrollTop;
    if (top !== previousTop) element.scrollTop = top;
    recordMainTimelineProgrammaticScrollOffset(element, previousTop);
};

const writeMainTimelineScrollOffset = (element: HTMLElement, offset: number, previousTop: number = element.scrollTop): void => {
    if (offset !== 0) element.scrollBy({ top: offset, behavior: 'instant' });
    recordMainTimelineProgrammaticScrollOffset(element, previousTop);
};

const consumeMainTimelineProgrammaticScrollOffset = (element: HTMLElement): number => {
    const offset = programmaticScrollOffsets.get(element) ?? 0;
    programmaticScrollOffsets.delete(element);
    return offset;
};

export { beginMainTimelineProgrammaticScroll, isMainTimelineProgrammaticScrollActive, MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE, consumeMainTimelineProgrammaticScrollOffset, isEditableKeyTarget, isMainTimelineKeyboardScrollEvent, isMainTimelineAtBottom, isMainTimelineAutoScrollLocked, isMainTimelineScrollRestoring, isMainTimelineMeasurementAtBottom, measureMainTimelineScroll, writeMainTimelineScrollOffset, writeMainTimelineScrollTop };
export type { MainTimelineScrollMeasurement };
