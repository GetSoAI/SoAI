/* SoAI - Shared UI image viewer geometry [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

type Point = Readonly<{ x: number; y: number }>;

const CONTENT_PREVIEW_IMAGE_MAX_SCALE = 10;

const resolveViewerOffsets = (imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number, nextScale: number, nextOffsetX: number, nextOffsetY: number): Point => {
    const scaledWidth = imageWidth * nextScale;
    const scaledHeight = imageHeight * nextScale;
    return {
        x: scaledWidth <= viewportWidth ? (viewportWidth - scaledWidth) / 2 : clampNumber(nextOffsetX, viewportWidth - scaledWidth, 0),
        y: scaledHeight <= viewportHeight ? (viewportHeight - scaledHeight) / 2 : clampNumber(nextOffsetY, viewportHeight - scaledHeight, 0)
    };
};

const computeFitScale = (imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number): number => {
    const fitScale = Math.min(viewportWidth / imageWidth, viewportHeight / imageHeight);
    return Math.min(1, fitScale);
};

const resistImageDisplacement = (displacement: number, extent: number): number => {
    const limit = extent * 0.15;
    return limit > 0 ? Math.sign(displacement) * limit * (1 - Math.exp(-Math.abs(displacement) / limit)) : 0;
};

const restoreImageDisplacement = (displacement: number, extent: number): number => {
    const limit = extent * 0.15;
    return limit > 0 ? -Math.sign(displacement) * limit * Math.log(1 - Math.min(Math.abs(displacement) / limit, 0.999999)) : 0;
};

const resolveElasticImageScale = (scale: number, minimum: number): number => {
    if (scale < minimum) {
        return Math.max(minimum * 0.84, minimum - (minimum - scale) * 0.2);
    }
    if (scale > CONTENT_PREVIEW_IMAGE_MAX_SCALE) {
        return Math.min(CONTENT_PREVIEW_IMAGE_MAX_SCALE * 1.08, CONTENT_PREVIEW_IMAGE_MAX_SCALE + (scale - CONTENT_PREVIEW_IMAGE_MAX_SCALE) * 0.08);
    }
    return scale;
};

export { computeFitScale, resolveViewerOffsets, resistImageDisplacement, restoreImageDisplacement, resolveElasticImageScale };
export { CONTENT_PREVIEW_IMAGE_MAX_SCALE };
export type { Point };
