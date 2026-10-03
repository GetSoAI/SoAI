/* SoAI - Shared frontend UI controls tabs wheel scroll [frontend/assets/ts/core/ui/controls/tabs/wheelScroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';
import { inlineDelta, readScrollInlineStart, scrollToInlineStart } from '@core/layout/direction.ts';
import { normalizeWheelDeltaPx } from '@core/ui/controls/wheelDelta.ts';

const TAB_WHEEL_SCROLL_EPSILON = 4;

const resolveTabsWheelScrollDelta = (scroller: HTMLElement, event: WheelEvent): number => {
    const deltaX = isFiniteNumber(event.deltaX) ? event.deltaX : 0;
    const deltaY = isFiniteNumber(event.deltaY) ? event.deltaY : 0;
    const selectedDelta = event.shiftKey && deltaY !== 0 ? deltaY : Math.abs(deltaX) > Math.abs(deltaY) ? inlineDelta(deltaX, scroller) : deltaY;
    return normalizeWheelDeltaPx(selectedDelta, event.deltaMode, scroller.clientWidth);
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
    const currentScroll = readScrollInlineStart(scroller);
    if ((delta < 0 && currentScroll <= epsilon) || (delta > 0 && currentScroll >= maxScrollLeft - epsilon)) {
        return false;
    }
    event.preventDefault();
    scrollToInlineStart(scroller, currentScroll + delta, 'instant');
    return true;
};

export { applyTabsWheelScroll, resolveTabsWheelScrollDelta };
