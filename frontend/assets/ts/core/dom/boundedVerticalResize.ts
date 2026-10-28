/* SoAI - Responsive content-bounded vertical resizing [frontend/assets/ts/core/dom/boundedVerticalResize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { parsePositiveCssPixelValue } from '@core/dom/attributes.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { getMatchMedia, getRequestAnimationFrame, getCancelAnimationFrame, getComputedStyleStrict, getMutationObserverCtor } from '@core/environment/public.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { AutoScroller } from '@core/ui/AutoScroller.ts';
import { readRootPosition, resolveCollectionScrollRoot, type CollectionScrollRoot } from '@core/data/boundedcollectionrenderer/scrollRoot.ts';

interface ResizeGesture {
    surface: HTMLElement;
    pointerId: number;
    startY: number;
    startHeight: number;
    minimum: number;
    maximum: number;
    pointerY: number;
    scrollRoot: CollectionScrollRoot;
    startScrollPosition: number;
    autoScroller: AutoScroller;
}

const bindBoundedVerticalResize = (root: HTMLElement, selector: string, signal: AbortSignal): void => {
    if (signal.aborted) return;
    const windowRef = root.ownerDocument.defaultView;
    if (windowRef === null) throw new Error('Resizable surfaces require an owning window');
    const media = getMatchMedia()('(pointer: fine)');
    const surfaces = new Map<HTMLElement, number | null>();
    let gesture: ResizeGesture | null = null;
    let frameId: number | null = null;
    const isEnabled = (): boolean => {
        const viewport = measureLayoutViewport(root);
        return media.matches && viewport.width >= 1024 && viewport.height >= 600;
    };
    const finish = (): void => {
        const current = gesture;
        gesture = null;
        if (frameId !== null) {
            getCancelAnimationFrame()(frameId);
            frameId = null;
        }
        current?.autoScroller.destroy();
        current?.surface.parentElement?.removeAttribute('data-resize-active');
        if (current !== null && current.surface.hasPointerCapture(current.pointerId)) current.surface.releasePointerCapture(current.pointerId);
    };
    const applySurfaceHeight = (surface: HTMLElement, height: number): void => {
        surface.style.height = `${height}px`;
        surface.style.setProperty('--resize-surface-max-height', `${height}px`);
    };
    const clearSurface = (surface: HTMLElement): void => {
        surface.removeAttribute('data-resizable-surface');
        surface.parentElement?.removeAttribute('data-resize-owner');
        surface.style.removeProperty('height');
        surface.style.removeProperty('--resize-surface-max-height');
        surfaces.delete(surface);
    };
    const reset = (): void => {
        finish();
        for (const surface of surfaces.keys()) clearSurface(surface);
        if (!signal.aborted) prepareTree(root);
    };
    const prepare = (target: EventTarget | null): HTMLElement | null => {
        if (!isEnabled() || !(target instanceof Element)) return null;
        const owner = target.closest('[data-resize-owner]');
        const surface = target.closest(selector) ?? (owner === null ? null : dom.resolve(selector, owner));
        if (!(surface instanceof HTMLElement) || !root.contains(surface) || surface.parentElement === null) return null;
        for (const registered of surfaces.keys()) if (!registered.isConnected) clearSurface(registered);
        const minimumHeight = surfaces.get(surface);
        if (minimumHeight === undefined) {
            surfaces.set(surface, null);
            surface.parentElement.setAttribute('data-resize-owner', 'true');
        }
        if (minimumHeight === undefined || minimumHeight === null) {
            if (surface.getAnimations().some((animation) => animation.playState === 'running')) return null;
            const box = measureLayoutBox(surface);
            if (box.width <= 0 || box.height <= 0) return null;
            surfaces.set(surface, box.height);
            applySurfaceHeight(surface, box.height);
            surface.setAttribute('data-resizable-surface', 'true');
        }
        return surface;
    };
    const begin = (event: Event): void => {
        if (!(event instanceof PointerEvent) || event.button !== 0 || gesture !== null) return;
        const surface = prepare(event.target);
        if (surface === null) return;
        const box = measureLayoutBox(surface);
        const point = measureLayoutPoint(event, surface);
        const owner = surface.parentElement;
        if (owner === null) throw new Error('Resize handle owner is unavailable');
        const ownerBox = measureLayoutBox(owner);
        const handleHeight = parsePositiveCssPixelValue(getComputedStyleStrict(owner).paddingBlockEnd, 0);
        if (handleHeight <= 0) throw new Error('Resize handle height must be positive');
        if (point.y < ownerBox.bottom - handleHeight || point.y > ownerBox.bottom || point.x < box.left || point.x > box.right) return;
        const minimum = surfaces.get(surface);
        if (minimum === undefined || minimum === null) throw new Error('Resizable surface baseline is unavailable');
        const contentHeight = surface.scrollHeight + surface.offsetHeight - surface.clientHeight;
        const scrollRoot = resolveCollectionScrollRoot(owner);
        const scrollViewportHeight = scrollRoot instanceof HTMLElement ? measureLayoutBox(scrollRoot).height : measureLayoutViewport(root).height;
        const maximum = Math.max(minimum, Math.min(contentHeight, scrollViewportHeight, measureLayoutViewport(root).height));
        event.preventDefault();
        surface.setPointerCapture(event.pointerId);
        surface.parentElement?.setAttribute('data-resize-active', 'true');
        gesture = { surface, pointerId: event.pointerId, startY: point.y, startHeight: box.height, minimum, maximum, pointerY: point.y, scrollRoot, startScrollPosition: readRootPosition(scrollRoot), autoScroller: new AutoScroller({ scrollContainer: scrollRoot }) };
        frameId = getRequestAnimationFrame()(tick);
    };
    const applyHeight = (current: ResizeGesture): number => {
        const scrollDelta = readRootPosition(current.scrollRoot) - current.startScrollPosition;
        const height = clampNumber(current.startHeight + current.pointerY - current.startY + scrollDelta, current.minimum, current.maximum);
        applySurfaceHeight(current.surface, height);
        return height;
    };
    const tick = (): void => {
        frameId = null;
        const current = gesture;
        if (current === null) return;
        if (!isEnabled() || !current.surface.isConnected || !current.surface.matches(selector)) {
            finish();
            return;
        }
        const height = applyHeight(current);
        if (current.autoScroller.update(current.pointerY, { upwardDistance: height - current.minimum, downwardDistance: current.maximum - height })) applyHeight(current);
        frameId = getRequestAnimationFrame()(tick);
    };
    const move = (event: Event): void => {
        const current = gesture;
        if (!(event instanceof PointerEvent) || current === null || event.pointerId !== current.pointerId) return;
        event.preventDefault();
        current.pointerY = measureLayoutPoint(event, current.surface).y;
        applyHeight(current);
    };
    const end = (event: Event): void => {
        if (event instanceof PointerEvent && gesture?.pointerId === event.pointerId) finish();
    };
    const prepareEvent = (event: Event): void => {
        prepare(event.target);
    };
    bindEventGroup(
        [
            { target: root, type: 'pointerover', listener: prepareEvent },
            { target: root, type: 'transitionend', listener: prepareEvent },
            { target: root, type: 'pointerdown', listener: begin, options: { capture: true } },
            { target: root.ownerDocument, type: 'pointermove', listener: move },
            { target: root.ownerDocument, type: 'pointerup', listener: end },
            { target: root.ownerDocument, type: 'pointercancel', listener: end },
            { target: root, type: 'lostpointercapture', listener: end },
            { target: windowRef, type: 'resize', listener: reset },
            { target: windowRef, type: 'blur', listener: finish },
            { target: windowRef, type: INTERFACE_SCALE_CHANGED_EVENT, listener: reset },
            { target: media, type: 'change', listener: reset }
        ],
        signal
    );
    const prepareTree = (node: Element): void => {
        if (node.matches(selector)) prepare(node);
        for (const surface of dom.resolveAll(selector, node)) prepare(surface);
    };
    const MutationObserverConstructor = getMutationObserverCtor();
    const observer = new MutationObserverConstructor((records) => {
        for (const surface of surfaces.keys()) {
            if (!surface.isConnected || !surface.matches(selector)) {
                if (gesture?.surface === surface) finish();
                clearSurface(surface);
            }
        }
        for (const record of records) {
            if (record.type === 'attributes' && record.target instanceof Element) prepareTree(record.target);
            for (const node of record.addedNodes) if (node instanceof Element) prepareTree(node);
        }
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-collapsed'] });
    prepareTree(root);
    signal.addEventListener(
        'abort',
        () => {
            observer.disconnect();
            reset();
        },
        { once: true }
    );
};

const isBoundedVerticalResizeGesture = (event: Event): boolean => event instanceof PointerEvent && event.defaultPrevented && event.target instanceof Element && event.target.closest('[data-resize-active="true"]') !== null;

const preserveBoundedVerticalResizeState = (existing: HTMLElement, created: HTMLElement): void => {
    if (existing.getAttribute('data-resize-owner') === 'true') created.setAttribute('data-resize-owner', 'true');
    if (existing.getAttribute('data-resize-active') === 'true') created.setAttribute('data-resize-active', 'true');
    if (existing.getAttribute('data-resizable-surface') !== 'true') return;
    created.setAttribute('data-resizable-surface', 'true');
    created.style.height = existing.style.height;
    created.style.setProperty('--resize-surface-max-height', existing.style.getPropertyValue('--resize-surface-max-height'));
};

export { bindBoundedVerticalResize, isBoundedVerticalResizeGesture, preserveBoundedVerticalResizeState };
