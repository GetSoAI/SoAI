/* SoAI - Shared layout space [frontend/assets/ts/core/layout/header/actionzonemanager/space.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { getWindow } from '@core/environment/public.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import type { ActionEntry, ActionZoneManagerHost, ActionZoneManagerState } from '@core/layout/header/actionzonemanager/types.ts';

const SPACE_SUPPRESSED_CLASS = 'header-action-button--space-suppressed';

const readPixelValue = (value: string): number => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

const resolveHTMLElement = (element: Element | null): HTMLElement | null => (element instanceof HTMLElement ? element : null);

const getVisibleChildren = (element: HTMLElement): HTMLElement[] => Array.from(element.children).filter((child): child is HTMLElement => child instanceof HTMLElement && child.getClientRects().length > 0);

const readStylePixelValue = (style: CSSStyleDeclaration, property: string): number => readPixelValue(style.getPropertyValue(property));

const readColumnGap = (element: HTMLElement): number => {
    const style = getWindow().getComputedStyle(element);
    const columnGap = readStylePixelValue(style, 'column-gap');
    return columnGap > 0 ? columnGap : readStylePixelValue(style, 'gap');
};

const readElementWidth = (element: HTMLElement): number => {
    const rectWidth = measureLayoutBox(element).width;
    if (rectWidth > 0) {
        return rectWidth;
    }
    return readStylePixelValue(getWindow().getComputedStyle(element), 'width');
};

const readHorizontalMargin = (element: HTMLElement): number => {
    const style = getWindow().getComputedStyle(element);
    return readStylePixelValue(style, 'margin-left') + readStylePixelValue(style, 'margin-right');
};

const readOuterWidth = (element: HTMLElement): number => readElementWidth(element) + readHorizontalMargin(element);

const readRequiredWidth = (element: HTMLElement): number => {
    const children = getVisibleChildren(element);
    if (!children.length) {
        return 0;
    }
    const childWidth = children.reduce((total, child) => total + readOuterWidth(child), 0);
    return childWidth + readColumnGap(element) * Math.max(0, children.length - 1);
};

const readRequiredWidthWithReplacement = (element: HTMLElement, replacementElement: HTMLElement, replacementWidth: number): number => {
    const children = getVisibleChildren(element);
    if (!children.length) {
        return 0;
    }
    const childWidth = children.reduce((total, child) => total + (child === replacementElement ? replacementWidth + readHorizontalMargin(child) : readOuterWidth(child)), 0);
    return childWidth + readColumnGap(element) * Math.max(0, children.length - 1);
};

const readContentWidth = (element: HTMLElement): number => {
    const style = getWindow().getComputedStyle(element);
    const horizontalPadding = readStylePixelValue(style, 'padding-left') + readStylePixelValue(style, 'padding-right');
    return Math.max(0, element.clientWidth - horizontalPadding);
};

const resolveActionEntry = (state: ActionZoneManagerState, actionId: string): ActionEntry | null => {
    const entry = state.actions.get(actionId);
    if (!entry || !state.container || entry.element.parentElement !== state.container) {
        return null;
    }
    return entry;
};

const isSpaceSuppressed = (entry: ActionEntry): boolean => entry.element.classList.contains(SPACE_SUPPRESSED_CLASS);

const resolveVisibleOptionalEntries = (entries: ActionEntry[]): ActionEntry[] => entries.filter((entry) => !isSpaceSuppressed(entry) && entry.element.getClientRects().length > 0);

const calculateVisibleContribution = (actionZone: HTMLElement, optionalEntries: ActionEntry[]): number => {
    const visibleActionCount = getVisibleChildren(actionZone).length;
    const visibleOptionalEntries = resolveVisibleOptionalEntries(optionalEntries);
    if (!visibleOptionalEntries.length) {
        return 0;
    }
    const actionGap = readColumnGap(actionZone);
    const nextVisibleActionCount = visibleActionCount - visibleOptionalEntries.length;
    const removedGapCount = Math.max(0, visibleActionCount - 1) - Math.max(0, nextVisibleActionCount - 1);
    return visibleOptionalEntries.reduce((total, entry) => total + readElementWidth(entry.element), 0) + actionGap * removedGapCount;
};

const calculateAllowedOptionalCount = (headerElement: HTMLElement, actionZone: HTMLElement, optionalEntries: ActionEntry[]): number => {
    const actionHost = resolveHTMLElement(actionZone.parentElement);
    if (!actionHost) {
        return 0;
    }
    const visibleContribution = calculateVisibleContribution(actionZone, optionalEntries);
    const actionHostRequiredWidth = Math.max(0, readRequiredWidth(actionHost) - visibleContribution);
    const headerRequiredWidth = readRequiredWidthWithReplacement(headerElement, actionHost, actionHostRequiredWidth);
    let remainingWidth = readContentWidth(headerElement) - headerRequiredWidth;
    let visibleActionCount = getVisibleChildren(actionZone).length - resolveVisibleOptionalEntries(optionalEntries).length;
    let allowedCount = 0;
    const actionGap = readColumnGap(actionZone);
    for (const entry of optionalEntries) {
        const width = readElementWidth(entry.element);
        const requiredWidth = width + (visibleActionCount > 0 ? actionGap : 0);
        if (remainingWidth < requiredWidth) {
            return allowedCount;
        }
        remainingWidth -= requiredWidth;
        visibleActionCount += 1;
        allowedCount += 1;
    }
    return allowedCount;
};

const updateActionSpace = (state: ActionZoneManagerState, host: ActionZoneManagerHost): void => {
    const headerElement = host.getDom('header');
    if (!headerElement || !headerElement.isConnected) {
        return;
    }
    const actionZone = resolveHTMLElement(state.container);
    if (!actionZone) {
        return;
    }

    const scrollEntry = resolveActionEntry(state, HEADER_ACTION_IDS.scrollToTop);
    const restartEntry = resolveActionEntry(state, HEADER_ACTION_IDS.restartReminder);
    const optionalEntries = [scrollEntry, restartEntry].filter((entry): entry is ActionEntry => entry !== null);
    const allowedCount = calculateAllowedOptionalCount(headerElement, actionZone, optionalEntries);
    optionalEntries.forEach((entry, index) => {
        entry.element.classList.toggle(SPACE_SUPPRESSED_CLASS, index >= allowedCount);
    });
};

const queueActionZoneSpaceUpdate = (state: ActionZoneManagerState, host: ActionZoneManagerHost): void => {
    const windowRef = getWindow();
    if (state.layoutFrameId !== null) {
        windowRef.cancelAnimationFrame(state.layoutFrameId);
    }
    state.layoutFrameId = windowRef.requestAnimationFrame(() => {
        state.layoutFrameId = null;
        updateActionSpace(state, host);
    });
};

const bindActionZoneSpaceUpdates = (state: ActionZoneManagerState, host: ActionZoneManagerHost): void => {
    const windowRef = getWindow();
    const headerElement = resolveHTMLElement(host.getDom('header'));
    const actionZone = resolveHTMLElement(state.container);
    const resizeHandler = (): void => queueActionZoneSpaceUpdate(state, host);
    const cleanupWindow = host.on(windowRef, 'resize', resizeHandler);
    const cleanupScale = host.on(windowRef, INTERFACE_SCALE_CHANGED_EVENT, resizeHandler);
    const observers: ResizeObserver[] = [];
    if (typeof ResizeObserver === 'function') {
        const observer = new ResizeObserver(resizeHandler);
        if (headerElement) {
            observer.observe(headerElement);
        }
        if (actionZone) {
            observer.observe(actionZone);
        }
        observers.push(observer);
    }
    state.layoutCleanup = () => {
        if (typeof cleanupWindow === 'function') {
            cleanupWindow();
        }
        if (typeof cleanupScale === 'function') {
            cleanupScale();
        }
        observers.forEach((observer) => observer.disconnect());
        if (state.layoutFrameId !== null) {
            windowRef.cancelAnimationFrame(state.layoutFrameId);
            state.layoutFrameId = null;
        }
    };
};

export { bindActionZoneSpaceUpdates, queueActionZoneSpaceUpdate };
