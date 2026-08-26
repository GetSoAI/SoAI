/* SoAI - Shared modals geometry [frontend/assets/ts/core/modals/modalhost/geometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import type { Boundaries, ResizeState } from '@core/modals/modalhost/types.ts';
import type { Position } from '@core/modals/types.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';

interface ModalFrameBounds {
    left: number;
    top: number;
    right: number;
    bottom: number;
    width: number;
    height: number;
}

interface TranslateBoundsInput {
    content: Element;
    width: number;
    height: number;
    isMobileViewport?: boolean;
}

interface ClientRectPositionInput extends TranslateBoundsInput {
    left: number;
    top: number;
}

interface ResizeResult {
    width: number;
    height: number;
    position: Position;
}

const parsePixelValue = (value: string): number | null => {
    const parsed = Number.parseFloat(value.trim());
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const resolveCollapsedSidebarWidth = (sidebar: HTMLElement): number | null => {
    const sidebarStyles = getComputedStyle(sidebar);
    const sidebarValue = parsePixelValue(sidebarStyles.getPropertyValue('--sidebar-width-collapsed'));
    if (sidebarValue !== null) {
        return sidebarValue;
    }

    const root = sidebar.ownerDocument.documentElement;
    const rootValue = parsePixelValue(getComputedStyle(root).getPropertyValue('--sidebar-collapsed-width'));
    return rootValue;
};

const resolveVisibleSidebarBoundary = (content: Element): number => {
    const sidebar = dom.resolve('.sidebar', content.ownerDocument);
    if (!(sidebar instanceof HTMLElement)) {
        return 0;
    }

    const styles = getComputedStyle(sidebar);
    if (styles.display === 'none' || styles.visibility === 'hidden') {
        return 0;
    }

    const rect = measureLayoutBox(sidebar);
    if (rect.width <= 0 || rect.height <= 0 || rect.right <= 0) {
        return 0;
    }

    const collapsedWidth = resolveCollapsedSidebarWidth(sidebar) ?? rect.width;
    return Math.max(0, Math.min(rect.right, rect.left + collapsedWidth));
};

const synchronizeModalFrame = (modal: HTMLElement, isMobileViewport: boolean): void => {
    const left = isMobileViewport ? 0 : resolveVisibleSidebarBoundary(modal);
    dom.setStyle(modal, '--modal-frame-left', `${left}px`);
};

const resolveModalFrameBounds = (content: Element, isMobileViewport = false): ModalFrameBounds => {
    const modal = content.closest('.ui-modal');
    if (modal instanceof HTMLElement) {
        const rect = measureLayoutBox(modal);
        const left = isMobileViewport || rect.left <= 0 ? rect.left : Math.max(rect.left, resolveVisibleSidebarBoundary(content));
        const right = Math.max(left + 1, rect.right);
        return {
            left,
            top: rect.top,
            right,
            bottom: rect.bottom,
            width: Math.max(right - left, 1),
            height: Math.max(rect.height, 1)
        };
    }

    throw new Error('Modal content must be mounted inside a modal root');
};

const calculateModalPositionFromClientRect = ({ content, left, top, width, height, isMobileViewport = false }: ClientRectPositionInput): Position => {
    const frame = resolveModalFrameBounds(content, isMobileViewport);
    return {
        x: left + width / 2 - (frame.left + frame.width / 2),
        y: top + height / 2 - (frame.top + frame.height / 2)
    };
};

const calculateModalTranslateBoundaries = ({ content, width, height, isMobileViewport = false }: TranslateBoundsInput): Boundaries => {
    const frame = resolveModalFrameBounds(content, isMobileViewport);
    const baseLeft = (frame.width - width) / 2;
    const baseTop = (frame.height - height) / 2;

    let minX = -baseLeft;
    let maxX = frame.width - width - baseLeft;
    if (minX > maxX) {
        minX = maxX;
    }

    let minY = -baseTop;
    let maxY = frame.height - height - baseTop;
    if (minY > maxY) {
        minY = maxY;
    }

    return { minX, maxX, minY, maxY };
};

const calculateAnchoredResize = ({ resizeState, deltaX, deltaY, isMobileViewport = false }: { resizeState: ResizeState; deltaX: number; deltaY: number; isMobileViewport?: boolean }): ResizeResult => {
    const frame = resolveModalFrameBounds(resizeState.modalContent, isMobileViewport);

    let left = resizeState.startLeft;
    let right = resizeState.startRight;
    let top = resizeState.startTop;
    let bottom = resizeState.startBottom;

    if (resizeState.edges.right) {
        right = clampNumber(resizeState.startRight + deltaX, resizeState.startLeft + resizeState.minWidth, Math.min(resizeState.startLeft + resizeState.maxWidth, frame.right));
    }
    if (resizeState.edges.left) {
        left = clampNumber(resizeState.startLeft + deltaX, Math.max(resizeState.startRight - resizeState.maxWidth, frame.left), resizeState.startRight - resizeState.minWidth);
    }
    if (resizeState.edges.bottom) {
        bottom = clampNumber(resizeState.startBottom + deltaY, resizeState.startTop + resizeState.minHeight, Math.min(resizeState.startTop + resizeState.maxHeight, frame.bottom));
    }
    if (resizeState.edges.top) {
        top = clampNumber(resizeState.startTop + deltaY, Math.max(resizeState.startBottom - resizeState.maxHeight, frame.top), resizeState.startBottom - resizeState.minHeight);
    }

    const width = clampNumber(right - left, resizeState.minWidth, resizeState.maxWidth);
    const height = clampNumber(bottom - top, resizeState.minHeight, resizeState.maxHeight);
    return {
        width,
        height,
        position: calculateModalPositionFromClientRect({
            content: resizeState.modalContent,
            left,
            top,
            width,
            height,
            isMobileViewport
        })
    };
};

export { calculateAnchoredResize, calculateModalPositionFromClientRect, calculateModalTranslateBoundaries, resolveModalFrameBounds, synchronizeModalFrame };
