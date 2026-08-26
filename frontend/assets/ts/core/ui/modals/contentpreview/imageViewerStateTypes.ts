/* SoAI - Content preview image viewer state contracts [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerStateTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';

type ContentPreviewImageViewerState = Readonly<{
    isReady: () => boolean;
    getTransform: () => Readonly<{ scale: number; offsetX: number; offsetY: number; fitMode: boolean }>;
    scheduleMinimapHide: (delayMs: number) => void;
    applyTransform: (nextScale: number, nextOffsetX: number, nextOffsetY: number, showMinimap: boolean) => boolean;
    fitToViewport: (showMinimap: boolean) => void;
    fitToViewportAt: (showMinimap: boolean, center: Point) => void;
    centerNative: (showMinimap: boolean) => void;
    centerNativeAt: (showMinimap: boolean, center: Point) => void;
    handleResize: () => void;
    handleImageLoad: () => void;
    handleImageError: () => void;
    dispose: () => void;
}>;

export type { ContentPreviewImageViewerState };
