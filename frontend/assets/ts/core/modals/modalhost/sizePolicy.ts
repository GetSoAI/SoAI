/* SoAI - Shared modals size policy [frontend/assets/ts/core/modals/modalhost/sizePolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { resolveModalLayoutContract } from '@core/modals/layoutPresets.ts';
import { resolveModalFrameBounds } from '@core/modals/modalhost/geometry.ts';
import type { ModalSizeDependencies, SizeConstraintResult, SizeLimits } from '@core/modals/modalhost/types.ts';
import type { ModalConfig, SavedModalState, Size } from '@core/modals/types.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const RESTORED_SIZE_MAX_FRAME_RATIO = 0.92;
const MIN_MODAL_DIMENSION = 1;

interface ModalViewportFrame {
    width: number;
    height: number;
}

const resolveModalFrame = (content: HTMLElement, isMobileViewport: boolean): ModalViewportFrame => {
    const frame = resolveModalFrameBounds(content, isMobileViewport);
    return {
        width: Math.max(frame.width, MIN_MODAL_DIMENSION),
        height: Math.max(frame.height, MIN_MODAL_DIMENSION)
    };
};

const buildSizeLimits = (frame: ModalViewportFrame, config: ModalConfig, isMobileViewport: boolean, layoutOverride: ModalConfig['size'] | undefined = undefined): SizeLimits => {
    const layout = layoutOverride === undefined ? config : resolveModalLayoutContract(layoutOverride);

    if (isMobileViewport) {
        return {
            minWidth: frame.width,
            minHeight: frame.height,
            maxWidth: frame.width,
            maxHeight: frame.height
        };
    }

    const maxWidthCandidate = isFiniteNumber(config.maxWidth) ? config.maxWidth : frame.width;
    const maxHeightCandidate = isFiniteNumber(config.maxHeight) ? config.maxHeight : frame.height;
    const maxWidth = clampNumber(maxWidthCandidate, MIN_MODAL_DIMENSION, frame.width);
    const maxHeight = clampNumber(maxHeightCandidate, MIN_MODAL_DIMENSION, frame.height);
    return {
        minWidth: clampNumber(layout.minWidth, MIN_MODAL_DIMENSION, maxWidth),
        minHeight: clampNumber(layout.minHeight, MIN_MODAL_DIMENSION, maxHeight),
        maxWidth,
        maxHeight
    };
};

const resolveContentSizeLimits = (content: HTMLElement, config: ModalConfig, isMobileViewport: boolean, layoutOverride: ModalConfig['size'] | undefined = undefined): SizeLimits => {
    return buildSizeLimits(resolveModalFrame(content, isMobileViewport), config, isMobileViewport, layoutOverride);
};

const resolveRestoredDimension = (value: number | undefined, min: number, max: number): number | null => {
    if (!isFiniteNumber(value)) {
        return null;
    }
    const clamped = clampNumber(value, min, max);
    if (clamped >= max * RESTORED_SIZE_MAX_FRAME_RATIO) {
        return null;
    }
    return clamped;
};

const resolveDefaultDimension = (value: number | null, min: number, max: number): number | null => {
    return isFiniteNumber(value) ? clampNumber(value, min, max) : null;
};

const resolvePreferredSize = (savedState: SavedModalState | null | undefined, config: ModalConfig, limits: SizeLimits): Partial<Size> | null => {
    const preferred: Partial<Size> = {};
    const savedWidth = resolveRestoredDimension(savedState?.size?.width, limits.minWidth, limits.maxWidth);
    const savedHeight = resolveRestoredDimension(savedState?.size?.height, limits.minHeight, limits.maxHeight);

    if (savedWidth !== null) {
        preferred.width = savedWidth;
    }
    if (savedHeight !== null) {
        preferred.height = savedHeight;
    }
    if (!Object.keys(preferred).length) {
        const defaultWidth = resolveDefaultDimension(config.defaultWidth, limits.minWidth, limits.maxWidth);
        const defaultHeight = resolveDefaultDimension(config.defaultHeight, limits.minHeight, limits.maxHeight);
        if (defaultWidth !== null) {
            preferred.width = defaultWidth;
        }
        if (defaultHeight !== null) {
            preferred.height = defaultHeight;
        }
    }
    return Object.keys(preferred).length ? preferred : null;
};

const resetSizeStyles = (content: HTMLElement): void => {
    dom.setStyles(content, {
        width: '',
        height: '',
        minWidth: '',
        minHeight: '',
        maxWidth: '',
        maxHeight: ''
    });
};

const applySizeConstraints = ({ content, config, isMobileViewport, savedState = null, layoutOverride = undefined }: ModalSizeDependencies): SizeConstraintResult | null => {
    if (!(content instanceof HTMLElement)) {
        return null;
    }

    const limits = resolveContentSizeLimits(content, config, isMobileViewport, layoutOverride);
    if (isMobileViewport) {
        dom.setStyles(content, {
            width: `${limits.maxWidth}px`,
            height: `${limits.maxHeight}px`,
            minWidth: `${limits.minWidth}px`,
            minHeight: `${limits.minHeight}px`,
            maxWidth: `${limits.maxWidth}px`,
            maxHeight: `${limits.maxHeight}px`,
            transform: ''
        });
        const after = measureLayoutBox(content);
        return { width: after.width, height: after.height, limits, changed: true };
    }

    const before = measureLayoutBox(content);
    const styles: Record<string, string> = { minWidth: `${limits.minWidth}px`, minHeight: `${limits.minHeight}px` };
    if (config.dynamic) {
        styles['maxWidth'] = `${limits.maxWidth}px`;
        styles['maxHeight'] = `${limits.maxHeight}px`;
    }

    const preferredSize = resolvePreferredSize(config.resizable ? savedState : null, config, limits);
    const targetWidth = preferredSize && isFiniteNumber(preferredSize.width) ? preferredSize.width : null;
    const targetHeight = preferredSize && isFiniteNumber(preferredSize.height) ? preferredSize.height : null;

    if (targetWidth !== null) {
        styles['width'] = `${clampNumber(targetWidth, limits.minWidth, limits.maxWidth)}px`;
    }
    if (targetHeight !== null) {
        styles['height'] = `${clampNumber(targetHeight, limits.minHeight, limits.maxHeight)}px`;
    }
    dom.setStyles(content, styles);
    const after = measureLayoutBox(content);
    return {
        width: after.width,
        height: after.height,
        limits,
        changed: Math.round(before.width) !== Math.round(after.width) || Math.round(before.height) !== Math.round(after.height)
    };
};

export { applySizeConstraints, resetSizeStyles, resolveContentSizeLimits };
