/* SoAI - Shared frontend UI controls tabs wheel scroll [frontend/assets/ts/core/ui/controls/tabs/wheelScroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';

const TAB_WHEEL_SCROLL_EPSILON = 4;
const LINE_WHEEL_DELTA_PX = 16;

const normalizeWheelDelta = (scroller: HTMLElement, event: WheelEvent, value: number): number => {
    if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) {
        return value * LINE_WHEEL_DELTA_PX;
    }
    if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
        return value * Math.max(scroller.clientWidth, 1);
    }
    return value;
};

const resolveTabsWheelScrollDelta = (scroller: HTMLElement, event: WheelEvent): number => {
    const deltaX = isFiniteNumber(event.deltaX) ? event.deltaX : 0;
    const deltaY = isFiniteNumber(event.deltaY) ? event.deltaY : 0;
    const selectedDelta = event.shiftKey && deltaY !== 0 ? deltaY : Math.abs(deltaX) > Math.abs(deltaY) ? deltaX : deltaY;
    return normalizeWheelDelta(scroller, event, selectedDelta);
};

const applyTabsWheelScroll = (scroller: HTMLElement, event: WheelEvent, epsilon = TAB_WHEEL_SCROLL_EPSILON): boolean => {
    const maxScrollLeft = Math.max(scroller.scrollWidth - scroller.clientWidth, 0);
    if (maxScrollLeft <= epsilon) {
        return false;
    }
    const delta = resolveTabsWheelScrollDelta(scroller, event);
    if (delta === 0) {
        return false;
    }
    const currentScroll = scroller.scrollLeft;
    if ((delta < 0 && currentScroll <= epsilon) || (delta > 0 && currentScroll >= maxScrollLeft - epsilon)) {
        return false;
    }
    event.preventDefault();
    scroller.scrollLeft += delta;
    return true;
};

export { applyTabsWheelScroll, resolveTabsWheelScrollDelta };
