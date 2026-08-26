/* SoAI - Shared UI image viewer minimap projection [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerMinimapProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

type MinimapProjection = Readonly<{
    translateX: number;
    translateY: number;
    width: number;
    height: number;
    zoomLabel: string;
}>;

const computeMinimapProjection = (imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number, minimapWidth: number, minimapHeight: number, scale: number, offsetX: number, offsetY: number): MinimapProjection => {
    const visibleLeft = clampNumber((0 - offsetX) / scale, 0, imageWidth);
    const visibleTop = clampNumber((0 - offsetY) / scale, 0, imageHeight);
    const visibleRight = clampNumber((viewportWidth - offsetX) / scale, 0, imageWidth);
    const visibleBottom = clampNumber((viewportHeight - offsetY) / scale, 0, imageHeight);
    const xScale = minimapWidth / imageWidth;
    const yScale = minimapHeight / imageHeight;
    return Object.freeze({
        translateX: visibleLeft * xScale,
        translateY: visibleTop * yScale,
        width: Math.max(2, (visibleRight - visibleLeft) * xScale),
        height: Math.max(2, (visibleBottom - visibleTop) * yScale),
        zoomLabel: `${Math.round(scale * 100)}%`
    });
};

export { computeMinimapProjection };
export type { MinimapProjection };
