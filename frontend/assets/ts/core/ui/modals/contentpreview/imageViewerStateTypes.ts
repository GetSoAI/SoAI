/* SoAI - Content preview image viewer state contracts [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerStateTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ContentPreviewImageViewerState = Readonly<{
    isReady: () => boolean;
    getTransform: () => Readonly<{ scale: number; offsetX: number; offsetY: number; fitMode: boolean }>;
    getGeometry: () => Readonly<{ imageWidth: number; imageHeight: number; viewportWidth: number; viewportHeight: number; fitScale: number }>;
    subscribeResize: (listener: () => void) => () => void;
    scheduleMinimapHide: (delayMs: number) => void;
    applyTransform: (nextScale: number, nextOffsetX: number, nextOffsetY: number, showMinimap: boolean, elastic?: boolean) => boolean;
    fitToViewport: (showMinimap: boolean) => void;
    handleResize: () => void;
    handleImageLoad: () => void;
    handleImageError: () => void;
    dispose: () => void;
}>;

export type { ContentPreviewImageViewerState };
