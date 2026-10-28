/* SoAI - Shared layout sidebar hover peek [frontend/assets/ts/core/layout/sidebar/hoverPeek.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureViewportBox, measureViewportPoint } from '@core/layout/elementGeometry.ts';
import { resolveModalCloseTrigger } from '@core/modals/modalhost/guards.ts';
import type { SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';

const SIDEBAR_PEEK_OPEN_DELAY_MS = 250;
const SIDEBAR_PEEK_CLOSE_DELAY_MS = 600;

interface SidebarHoverPeekHost {
    addSessionDisposer: (functionValue: SidebarDisposerCandidate) => void;
    on: (target: EventTarget, eventName: string, handler: (event: Event) => void) => SidebarDisposerCandidate;
    getDomRef: (key: string) => HTMLElement | null;
    canHoverPeek: () => boolean;
    isHoverPeeking: () => boolean;
    setHoverPeek: (peeking: boolean) => void;
    setTimer: (handler: () => void, delay: number) => number | null;
    clearTimer: (timerId: number) => void;
}

const isMousePointerEvent = (event: Event): boolean => !(event instanceof PointerEvent) || event.pointerType === 'mouse';

const bindSidebarHoverPeek = (host: SidebarHoverPeekHost): void => {
    const hamburger = host.getDomRef('hamburger');
    const sidebar = host.getDomRef('sidebar');
    if (!hamburger || !sidebar) {
        throw new Error('Sidebar and hamburger are required for hover peek behavior');
    }

    let openTimer: number | null = null;
    let closeTimer: number | null = null;
    let hoverSuppressedUntilLeave = false;
    let carriedCloseControl: Element | null = null;
    const clearCarriedHover = (): void => {
        hamburger.removeAttribute('data-hover-carried');
        carriedCloseControl?.removeAttribute('data-hover-carried');
        carriedCloseControl = null;
    };

    const clearOpenTimer = (): void => {
        if (openTimer !== null) host.clearTimer(openTimer);
        openTimer = null;
    };
    const clearCloseTimer = (): void => {
        if (closeTimer !== null) host.clearTimer(closeTimer);
        closeTimer = null;
    };
    const containsTarget = (surface: Element, target: EventTarget | null): boolean => target instanceof Node && surface.contains(target);
    const open = (): void => {
        openTimer = null;
        if (!hoverSuppressedUntilLeave && host.canHoverPeek()) host.setHoverPeek(true);
    };
    const close = (): void => {
        closeTimer = null;
        if (host.isHoverPeeking()) host.setHoverPeek(false);
    };
    const scheduleClose = (): void => {
        clearCloseTimer();
        closeTimer = host.setTimer(close, SIDEBAR_PEEK_CLOSE_DELAY_MS);
    };

    const isOverHamburger = (event: MouseEvent): boolean => {
        const bounds = measureViewportBox(hamburger);
        const point = measureViewportPoint(event);
        return point.x >= bounds.left && point.x < bounds.right && point.y >= bounds.top && point.y < bounds.bottom;
    };
    host.addSessionDisposer(
        host.on(hamburger.ownerDocument, 'pointerdown', (event: Event) => {
            if (!(event instanceof MouseEvent) || !isMousePointerEvent(event) || event.button !== 0 || !(event.target instanceof Element)) return;
            const closeControl = resolveModalCloseTrigger(event.target);
            if (!closeControl?.closest('[data-modal-presentation="viewport"]') || !isOverHamburger(event)) return;
            clearCarriedHover();
            carriedCloseControl = closeControl;
            closeControl.setAttribute('data-hover-carried', '');
            hamburger.setAttribute('data-hover-carried', '');
            hoverSuppressedUntilLeave = true;
            clearOpenTimer();
            clearCloseTimer();
            if (host.isHoverPeeking()) host.setHoverPeek(false);
        })
    );
    host.addSessionDisposer(
        host.on(hamburger.ownerDocument, 'pointermove', (event: Event) => {
            if (!hoverSuppressedUntilLeave || !(event instanceof MouseEvent) || !isMousePointerEvent(event) || isOverHamburger(event)) return;
            hoverSuppressedUntilLeave = false;
            clearCarriedHover();
        })
    );

    host.addSessionDisposer(
        host.on(hamburger, 'pointerenter', (event: Event) => {
            if (!isMousePointerEvent(event)) return;
            clearCloseTimer();
            if (!hoverSuppressedUntilLeave && host.canHoverPeek() && openTimer === null) {
                openTimer = host.setTimer(open, SIDEBAR_PEEK_OPEN_DELAY_MS);
            }
        })
    );
    host.addSessionDisposer(
        host.on(hamburger, 'pointerleave', (event: Event) => {
            if (!isMousePointerEvent(event)) return;
            hoverSuppressedUntilLeave = false;
            clearCarriedHover();
            clearOpenTimer();
            if (host.isHoverPeeking() && !containsTarget(sidebar, event instanceof MouseEvent ? event.relatedTarget : null)) scheduleClose();
        })
    );
    host.addSessionDisposer(
        host.on(sidebar, 'pointerenter', (event: Event) => {
            if (isMousePointerEvent(event) && host.isHoverPeeking()) clearCloseTimer();
        })
    );
    host.addSessionDisposer(
        host.on(sidebar, 'pointerleave', (event: Event) => {
            if (!isMousePointerEvent(event) || !host.isHoverPeeking()) return;
            if (!containsTarget(hamburger, event instanceof MouseEvent ? event.relatedTarget : null)) scheduleClose();
        })
    );
    host.addSessionDisposer(() => {
        clearCarriedHover();
        clearOpenTimer();
        clearCloseTimer();
        if (host.isHoverPeeking()) host.setHoverPeek(false);
    });
};

export { SIDEBAR_PEEK_CLOSE_DELAY_MS, SIDEBAR_PEEK_OPEN_DELAY_MS, bindSidebarHoverPeek };
export type { SidebarHoverPeekHost };
