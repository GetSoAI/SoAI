/* SoAI - Shared UI image viewer geometry [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

type Point = Readonly<{ x: number; y: number }>;

const CONTENT_PREVIEW_IMAGE_MIN_SCALE = 0.1;
const CONTENT_PREVIEW_IMAGE_MAX_SCALE = 10;

const resolveViewerOffsets = (imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number, nextScale: number, nextOffsetX: number, nextOffsetY: number): Point => {
    const scaledWidth = imageWidth * nextScale;
    const scaledHeight = imageHeight * nextScale;
    return {
        x: scaledWidth <= viewportWidth ? (viewportWidth - scaledWidth) / 2 : clampNumber(nextOffsetX, viewportWidth - scaledWidth, 0),
        y: scaledHeight <= viewportHeight ? (viewportHeight - scaledHeight) / 2 : clampNumber(nextOffsetY, viewportHeight - scaledHeight, 0)
    };
};

const computeFitScale = (imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number, minScale: number, maxScale: number): number => {
    const fitScale = Math.min(viewportWidth / imageWidth, viewportHeight / imageHeight);
    return clampNumber(fitScale, minScale, maxScale);
};

export { computeFitScale, resolveViewerOffsets };
export { CONTENT_PREVIEW_IMAGE_MIN_SCALE, CONTENT_PREVIEW_IMAGE_MAX_SCALE };
export type { Point };
