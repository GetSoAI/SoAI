/* SoAI - Shared modals modalhost validation [frontend/assets/ts/core/modals/modalhost/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClientPoint } from '@core/modals/modalhost/types.ts';
import { measureLayoutPoint, measureLayoutTouchPoint } from '@core/layout/elementGeometry.ts';

const getClientPoint = (event: Event, scope: Document | Element): ClientPoint | null => {
    if (event instanceof MouseEvent || event instanceof PointerEvent) {
        const point = measureLayoutPoint(event, scope);
        const clientX = point.x;
        const clientY = point.y;
        if (Number.isFinite(clientX) && Number.isFinite(clientY)) {
            return { clientX, clientY, isTouch: false };
        }
        return null;
    }
    const touchCtor: typeof TouchEvent | null = typeof TouchEvent === 'function' ? TouchEvent : null;
    if (touchCtor && event instanceof touchCtor) {
        const first = event.touches[0] ?? null;
        if (!first) {
            return null;
        }
        const point = measureLayoutTouchPoint(first, scope);
        const clientX = point.x;
        const clientY = point.y;
        if (Number.isFinite(clientX) && Number.isFinite(clientY)) {
            return { clientX, clientY, isTouch: true };
        }
    }
    return null;
};

const resolveClosestModalId = (element: Element | null): string | null => {
    const modal = element?.closest?.('.ui-modal');
    if (!(modal instanceof HTMLElement)) {
        return null;
    }
    const id = modal.id;
    return id ? id : null;
};

export { getClientPoint, resolveClosestModalId };
