/* SoAI - Delegated toggle switch pointer tracking and release [frontend/assets/ts/core/ui/controls/toggleswitch/dragRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { isRtl } from '@core/layout/direction.ts';
import { measureViewportBox, measureViewportPoint } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isActionToggleInteractionDisabled } from '@core/toggleSwitch.ts';

const TOGGLE_DRAG_PROGRESS_PROPERTY = '--toggle-drag-progress';

interface ToggleDrag {
    wrapper: HTMLElement;
    slider: HTMLElement;
    input: HTMLInputElement;
    pointerId: number;
    startX: number;
    startY: number;
    checked: boolean;
    travel: number;
    direction: number;
    startProgress: number;
    progress: number;
    dragging: boolean;
}

const isAvailable = (gesture: ToggleDrag): boolean => {
    const { wrapper, input, slider } = gesture;
    return wrapper.isConnected && wrapper.contains(input) && wrapper.contains(slider) && !wrapper.closest('[inert]') && !isActionToggleInteractionDisabled(wrapper) && wrapper.dataset['toggleLocked'] !== 'true' && !input.matches(':disabled') && input.getAttribute('aria-disabled') !== 'true' && (!input.readOnly || wrapper.classList.contains('toggle-switch--action')) && input.checked === gesture.checked;
};

const createToggleSwitchDragRuntime = (documentRef: Document) => {
    let cleanup: (() => void) | null = null;
    let active: ToggleDrag | null = null;
    let suppressed: HTMLElement | null = null;
    let suppressionTimer: ReturnType<typeof setTimeout> | null = null;
    const settling = new Map<HTMLElement, ReturnType<typeof setTimeout>>();

    const clearSuppression = (): void => {
        if (suppressionTimer !== null) clearTimeout(suppressionTimer);
        suppressionTimer = null;
        suppressed = null;
    };

    const suppressClick = (wrapper: HTMLElement): void => {
        clearSuppression();
        suppressed = wrapper;
        suppressionTimer = setTimeout(clearSuppression, 1000);
    };

    const clearSettling = (wrapper: HTMLElement): void => {
        const timer = settling.get(wrapper);
        if (timer !== undefined) clearTimeout(timer);
        settling.delete(wrapper);
        if (typeof wrapper.getAnimations === 'function') {
            for (const animation of wrapper.getAnimations()) {
                if ('transitionProperty' in animation && animation.transitionProperty === TOGGLE_DRAG_PROGRESS_PROPERTY) animation.cancel();
            }
        }
        delete wrapper.dataset['toggleDragSettling'];
        wrapper.style.removeProperty(TOGGLE_DRAG_PROGRESS_PROPERTY);
    };

    const finish = (commit: boolean): void => {
        const gesture = active;
        active = null;
        if (!gesture) return;
        const { wrapper, slider, input, pointerId, dragging } = gesture;
        const available = isAvailable(gesture);
        if (dragging) suppressClick(wrapper);
        if (slider.hasPointerCapture?.(pointerId)) slider.releasePointerCapture(pointerId);
        if (commit && dragging && available) {
            const checked = gesture.progress === 0.5 ? gesture.checked : gesture.progress > 0.5;
            if (checked !== gesture.checked) {
                if (wrapper.classList.contains('toggle-switch--action')) wrapper.click();
                else input.click();
            }
        }
        if (!dragging) {
            clearSettling(wrapper);
            return;
        }
        const target = input.checked || wrapper.classList.contains('toggle-switch--checked') ? 1 : 0;
        if (gesture.progress === target || !wrapper.isConnected) {
            delete wrapper.dataset['toggleDragging'];
            clearSettling(wrapper);
            return;
        }
        wrapper.dataset['toggleDragSettling'] = 'true';
        delete wrapper.dataset['toggleDragging'];
        const style = getComputedStyleStrict(wrapper);
        style.getPropertyValue(TOGGLE_DRAG_PROGRESS_PROPERTY);
        const duration = parseMaxCssDurationMs(style.transitionDuration);
        wrapper.style.setProperty(TOGGLE_DRAG_PROGRESS_PROPERTY, String(target));
        settling.set(
            wrapper,
            setTimeout(() => clearSettling(wrapper), duration + 50)
        );
    };

    const cancel = (): void => {
        if (active) suppressClick(active.wrapper);
        finish(false);
    };

    const pointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent) || event.button !== 0 || !event.isPrimary) return;
        if (active) {
            cancel();
            return;
        }
        clearSuppression();
        const slider = event.target instanceof Element ? event.target.closest('.toggle-switch > .slider') : null;
        const wrapper = slider?.parentElement;
        const input = wrapper ? dom.resolve(':scope > input[type="checkbox"]', wrapper) : null;
        if (!(slider instanceof HTMLElement) || !wrapper || !(input instanceof HTMLInputElement)) return;
        const width = measureViewportBox(slider).width;
        const travel = (Number.parseFloat(getComputedStyleStrict(slider).getPropertyValue('--toggle-handle-translate')) * width) / slider.offsetWidth;
        if (!Number.isFinite(travel) || travel <= 0) return;
        const position = measureViewportPoint(event);
        const gesture: ToggleDrag = {
            wrapper,
            slider,
            input,
            pointerId: event.pointerId,
            startX: position.x,
            startY: position.y,
            checked: input.checked,
            travel,
            direction: isRtl(slider) ? -1 : 1,
            startProgress: input.checked ? 1 : 0,
            progress: input.checked ? 1 : 0,
            dragging: false
        };
        if (!isAvailable(gesture)) return;
        active = gesture;
    };

    const pointerMove = (event: Event): void => {
        const gesture = active;
        if (!(event instanceof PointerEvent) || !gesture || event.pointerId !== gesture.pointerId) return;
        if (!isAvailable(gesture)) {
            cancel();
            return;
        }
        const position = measureViewportPoint(event);
        const horizontal = position.x - gesture.startX;
        const vertical = position.y - gesture.startY;
        if (!gesture.dragging) {
            if (Math.max(Math.abs(horizontal), Math.abs(vertical)) < 4) return;
            if (Math.abs(vertical) > Math.abs(horizontal)) {
                cancel();
                return;
            }
            if (settling.has(gesture.wrapper)) gesture.startProgress = Number(getComputedStyleStrict(gesture.wrapper).getPropertyValue(TOGGLE_DRAG_PROGRESS_PROPERTY));
            clearSettling(gesture.wrapper);
            gesture.dragging = true;
            gesture.wrapper.dataset['toggleDragging'] = 'true';
            gesture.slider.setPointerCapture?.(gesture.pointerId);
            if (gesture.wrapper.classList.contains('toggle-switch--action')) gesture.wrapper.focus({ preventScroll: true });
            else gesture.input.focus({ preventScroll: true });
        }
        event.preventDefault();
        gesture.progress = clampNumber(gesture.startProgress + (horizontal * gesture.direction) / gesture.travel, 0, 1);
        gesture.wrapper.style.setProperty(TOGGLE_DRAG_PROGRESS_PROPERTY, String(gesture.progress));
    };

    const pointerUp = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !active || event.pointerId !== active.pointerId) return;
        pointerMove(event);
        if (active?.dragging) event.preventDefault();
        finish(true);
    };

    const pointerCancel = (event: Event): void => {
        if (event instanceof PointerEvent && event.pointerId === active?.pointerId) cancel();
    };

    const click = (event: Event): void => {
        if (!(event instanceof MouseEvent) || event.detail === 0 || !suppressed || !(event.target instanceof Node) || !suppressed.contains(event.target)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    };

    const keyDown = (event: Event): void => {
        if (event instanceof KeyboardEvent && event.key === 'Escape') cancel();
    };

    const visibility = (): void => {
        if (documentRef.hidden) cancel();
    };

    return {
        initialize(): void {
            if (cleanup) return;
            const view = documentRef.defaultView;
            if (!view) throw new Error('Toggle switch dragging requires an owning window');
            cleanup = bindEventGroup([
                { target: documentRef, type: 'pointerdown', listener: pointerDown, options: true },
                { target: documentRef, type: 'pointermove', listener: pointerMove, options: { capture: true, passive: false } },
                { target: documentRef, type: 'pointerup', listener: pointerUp, options: true },
                { target: documentRef, type: 'pointercancel', listener: pointerCancel, options: true },
                { target: documentRef, type: 'lostpointercapture', listener: pointerCancel, options: true },
                { target: documentRef, type: 'click', listener: click, options: true },
                { target: documentRef, type: 'keydown', listener: keyDown, options: true },
                { target: documentRef, type: 'visibilitychange', listener: visibility },
                { target: view, type: 'blur', listener: cancel },
                { target: view, type: 'pagehide', listener: cancel }
            ]);
        },
        destroy(): void {
            cancel();
            cleanup?.();
            cleanup = null;
            clearSuppression();
            for (const wrapper of settling.keys()) clearSettling(wrapper);
        }
    };
};

export { createToggleSwitchDragRuntime };
