/* SoAI - Tooltip service DOM event bindings [frontend/assets/ts/core/ui/tooltips/tooltipEventBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { createTooltipAttributeObserver } from '@core/ui/tooltips/tooltipAttributeObserver.ts';

type TooltipEventBindingOptions = {
    documentRef: Document;
    view: Window | null;
    resources: ResourceTracker;
    attributeName: string;
    shouldShowOnFocus: (target: Element) => boolean;
    handleEnter: (target: Element) => void;
    handleLeave: (target: Element, relatedCandidate: EventTarget | null) => void;
    handleAttributeChanged: (target: Element) => void;
    handleResize: () => void;
    hide: () => void;
    setKeyboardModality: (isKeyboardModality: boolean) => void;
};

const resolveTooltipTarget = (candidate: EventTarget | null, attributeName: string): Element | null => {
    if (!(candidate instanceof Element)) {
        return null;
    }
    return candidate.closest(`[${attributeName}]`);
};

const bindTooltipServiceEvents = (options: TooltipEventBindingOptions): void => {
    const onPointerOver = (event: PointerEvent): void => {
        const nextTarget = resolveTooltipTarget(event.target, options.attributeName);
        if (nextTarget) {
            options.handleEnter(nextTarget);
        }
    };

    const onPointerOut = (event: PointerEvent): void => {
        const leavingTarget = resolveTooltipTarget(event.target, options.attributeName);
        if (leavingTarget) {
            options.handleLeave(leavingTarget, event.relatedTarget);
        }
    };

    const onFocusIn = (event: FocusEvent): void => {
        const nextTarget = resolveTooltipTarget(event.target, options.attributeName);
        if (nextTarget && options.shouldShowOnFocus(nextTarget)) {
            options.handleEnter(nextTarget);
        }
    };

    const onFocusOut = (event: FocusEvent): void => {
        const leavingTarget = resolveTooltipTarget(event.target, options.attributeName);
        if (leavingTarget) {
            options.handleLeave(leavingTarget, event.relatedTarget);
        }
    };

    const onKeyDown = (event: KeyboardEvent): void => {
        if (!event.metaKey && !event.ctrlKey && !event.altKey) {
            options.setKeyboardModality(true);
        }
        if (event.key === 'Escape') {
            options.hide();
        }
    };

    const onPointerDown = (): void => {
        options.setKeyboardModality(false);
        options.hide();
    };

    options.documentRef.addEventListener('pointerover', onPointerOver, true);
    options.documentRef.addEventListener('pointerout', onPointerOut, true);
    options.documentRef.addEventListener('focusin', onFocusIn, true);
    options.documentRef.addEventListener('focusout', onFocusOut, true);
    options.documentRef.addEventListener('keydown', onKeyDown, true);
    options.documentRef.addEventListener('pointerdown', onPointerDown, true);
    options.documentRef.addEventListener('scroll', options.hide, true);
    options.resources.track(options.documentRef, (doc) => {
        doc.removeEventListener('pointerover', onPointerOver, true);
        doc.removeEventListener('pointerout', onPointerOut, true);
        doc.removeEventListener('focusin', onFocusIn, true);
        doc.removeEventListener('focusout', onFocusOut, true);
        doc.removeEventListener('keydown', onKeyDown, true);
        doc.removeEventListener('pointerdown', onPointerDown, true);
        doc.removeEventListener('scroll', options.hide, true);
    });

    if (!options.view) {
        return;
    }
    const observer = createTooltipAttributeObserver({
        documentRef: options.documentRef,
        view: options.view,
        attributeName: options.attributeName,
        handleTarget: options.handleAttributeChanged
    });
    options.resources.track(observer, (trackedObserver) => trackedObserver.disconnect());
    options.view.addEventListener('resize', options.handleResize, true);
    options.view.addEventListener(INTERFACE_SCALE_CHANGED_EVENT, options.handleResize, true);
    options.resources.track(options.view, (win) => {
        win.removeEventListener('resize', options.handleResize, true);
        win.removeEventListener(INTERFACE_SCALE_CHANGED_EVENT, options.handleResize, true);
    });
};

export { bindTooltipServiceEvents };
