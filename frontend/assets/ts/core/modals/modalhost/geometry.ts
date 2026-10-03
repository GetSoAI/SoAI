/* SoAI - Shared modals geometry [frontend/assets/ts/core/modals/modalhost/geometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
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

const resolveModalFrameBounds = (content: Element): ModalFrameBounds => {
    const modal = content.closest('.ui-modal');
    if (modal instanceof HTMLElement) {
        const rect = measureLayoutBox(modal);
        const right = Math.max(rect.left + 1, rect.right);
        return {
            left: rect.left,
            top: rect.top,
            right,
            bottom: rect.bottom,
            width: Math.max(right - rect.left, 1),
            height: Math.max(rect.height, 1)
        };
    }

    throw new Error('Modal content must be mounted inside a modal root');
};

const calculateModalPositionFromClientRect = ({ content, left, top, width, height }: ClientRectPositionInput): Position => {
    const frame = resolveModalFrameBounds(content);
    return {
        x: left + width / 2 - (frame.left + frame.width / 2),
        y: top + height / 2 - (frame.top + frame.height / 2)
    };
};

const calculateModalTranslateBoundaries = ({ content, width, height }: TranslateBoundsInput): Boundaries => {
    const frame = resolveModalFrameBounds(content);
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

const calculateAnchoredResize = ({ resizeState, deltaX, deltaY }: { resizeState: ResizeState; deltaX: number; deltaY: number }): ResizeResult => {
    const frame = resolveModalFrameBounds(resizeState.modalContent);

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
            height
        })
    };
};

export { calculateAnchoredResize, calculateModalPositionFromClientRect, calculateModalTranslateBoundaries, resolveModalFrameBounds };
