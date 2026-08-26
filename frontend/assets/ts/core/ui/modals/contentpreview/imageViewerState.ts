/* SoAI - Content preview image viewer scene state [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { CONTENT_PREVIEW_IMAGE_MAX_SCALE, CONTENT_PREVIEW_IMAGE_MIN_SCALE, computeFitScale, resolveViewerOffsets, type Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import { applyContentPreviewImageViewerMetadata } from '@core/ui/modals/contentpreview/imageViewerMetadataState.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { createContentPreviewImageViewerMinimap } from '@core/ui/modals/contentpreview/imageViewerMinimap.ts';
import { computeMinimapProjection } from '@core/ui/modals/contentpreview/imageViewerMinimapProjection.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';
import type { ContentPreviewImageMetadata } from '@core/ui/modals/contentpreview/types.ts';

const createContentPreviewImageViewerState = (refs: ContentPreviewImageViewerRefs, sourceUrl: string, imageMetadata: ContentPreviewImageMetadata | null): ContentPreviewImageViewerState => {
    const resources = new ResourceTracker();
    const minimap = createContentPreviewImageViewerMinimap({ refs, resources });

    let imageWidth = 0;
    let imageHeight = 0;
    let scale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let fitMode = false;
    let minScale = CONTENT_PREVIEW_IMAGE_MIN_SCALE;
    const maxScale = CONTENT_PREVIEW_IMAGE_MAX_SCALE;
    let metadataAbort: AbortController | null = null;

    const updateZoom = (): void => {
        refs.zoom.value.textContent = `${Math.round(scale * 100)}%`;
    };

    const updateTransform = (): void => {
        refs.stage.style.transform = `translate3d(${offsetX}px, ${offsetY}px, 0) scale(${scale})`;
        updateZoom();
    };

    const updateMinimap = (): void => {
        if (!minimap.isVisible() || !imageWidth || !imageHeight) {
            return;
        }
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        const minimapWidth = refs.minimapFrame.clientWidth;
        const minimapHeight = refs.minimapFrame.clientHeight;
        if (!viewportWidth || !viewportHeight || !minimapWidth || !minimapHeight) {
            return;
        }
        const projection = computeMinimapProjection(imageWidth, imageHeight, viewportWidth, viewportHeight, minimapWidth, minimapHeight, scale, offsetX, offsetY);
        refs.minimapViewport.style.transform = `translate3d(${projection.translateX}px, ${projection.translateY}px, 0)`;
        refs.minimapViewport.style.width = `${projection.width}px`;
        refs.minimapViewport.style.height = `${projection.height}px`;
        refs.minimapZoom.textContent = projection.zoomLabel;
    };

    const render = (showMinimap: boolean): void => {
        updateTransform();
        if (showMinimap) {
            minimap.setVisible(true);
            updateMinimap();
            minimap.scheduleHide(900);
            return;
        }
        if (minimap.isVisible()) {
            updateMinimap();
        }
    };

    const resolveOffsets = (nextScale: number, nextOffsetX: number, nextOffsetY: number): Point => {
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        if (!imageWidth || !imageHeight || !viewportWidth || !viewportHeight) {
            return { x: nextOffsetX, y: nextOffsetY };
        }
        return resolveViewerOffsets(imageWidth, imageHeight, viewportWidth, viewportHeight, nextScale, nextOffsetX, nextOffsetY);
    };

    const computeFitScaleValue = (): number => {
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        if (!imageWidth || !imageHeight || !viewportWidth || !viewportHeight) {
            return scale;
        }
        return computeFitScale(imageWidth, imageHeight, viewportWidth, viewportHeight, minScale, maxScale);
    };

    const configureMinimapSize = (): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        const aspect = imageWidth / imageHeight;
        let width = 96;
        let height = width / aspect;
        if (height > 64) {
            height = 64;
            width = height * aspect;
        }
        refs.minimapFrame.style.width = `${Math.max(64, Math.round(width))}px`;
        refs.minimapFrame.style.height = `${Math.max(44, Math.round(height))}px`;
    };

    const applyTransform = (nextScale: number, nextOffsetX: number, nextOffsetY: number, showMinimap: boolean): boolean => {
        const clampedScale = clampNumber(nextScale, minScale, maxScale);
        const clampedOffsets = resolveOffsets(clampedScale, nextOffsetX, nextOffsetY);
        if (clampedScale === scale && clampedOffsets.x === offsetX && clampedOffsets.y === offsetY) {
            return false;
        }
        scale = clampedScale;
        offsetX = clampedOffsets.x;
        offsetY = clampedOffsets.y;
        fitMode = false;
        render(showMinimap);
        return true;
    };

    const fitToViewport = (showMinimap: boolean): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        fitMode = true;
        scale = computeFitScaleValue();
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        offsetX = viewportWidth ? (viewportWidth - imageWidth * scale) / 2 : 0;
        offsetY = viewportHeight ? (viewportHeight - imageHeight * scale) / 2 : 0;
        render(showMinimap);
    };

    const centerNative = (showMinimap: boolean): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        fitMode = false;
        scale = 1;
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        offsetX = viewportWidth ? (viewportWidth - imageWidth * scale) / 2 : 0;
        offsetY = viewportHeight ? (viewportHeight - imageHeight * scale) / 2 : 0;
        render(showMinimap);
    };

    const centerNativeAt = (showMinimap: boolean, center: Point): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        const currentTransform = state.getTransform();
        const contentX = (center.x - currentTransform.offsetX) / currentTransform.scale;
        const contentY = (center.y - currentTransform.offsetY) / currentTransform.scale;
        fitMode = false;
        scale = 1;
        offsetX = center.x - contentX * scale;
        offsetY = center.y - contentY * scale;
        const clamped = resolveOffsets(scale, offsetX, offsetY);
        offsetX = clamped.x;
        offsetY = clamped.y;
        render(showMinimap);
    };

    const fitToViewportAt = (showMinimap: boolean, center: Point): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        const currentTransform = state.getTransform();
        const contentX = (center.x - currentTransform.offsetX) / currentTransform.scale;
        const contentY = (center.y - currentTransform.offsetY) / currentTransform.scale;
        fitMode = true;
        scale = computeFitScaleValue();
        offsetX = center.x - contentX * scale;
        offsetY = center.y - contentY * scale;
        const clamped = resolveOffsets(scale, offsetX, offsetY);
        offsetX = clamped.x;
        offsetY = clamped.y;
        render(showMinimap);
    };

    const handleResize = (): void => {
        if (!imageWidth || !imageHeight) {
            return;
        }
        if (fitMode) {
            scale = computeFitScaleValue();
            const viewportWidth = refs.viewport.clientWidth;
            const viewportHeight = refs.viewport.clientHeight;
            offsetX = viewportWidth ? (viewportWidth - imageWidth * scale) / 2 : 0;
            offsetY = viewportHeight ? (viewportHeight - imageHeight * scale) / 2 : 0;
        } else {
            const clamped = resolveOffsets(scale, offsetX, offsetY);
            offsetX = clamped.x;
            offsetY = clamped.y;
        }
        render(false);
    };

    const handleImageLoad = (): void => {
        imageWidth = refs.image.naturalWidth;
        imageHeight = refs.image.naturalHeight;
        refs.stage.style.width = `${imageWidth}px`;
        refs.stage.style.height = `${imageHeight}px`;
        refs.resolution.value.textContent = `${imageWidth}x${imageHeight}`;
        configureMinimapSize();

        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        minScale = CONTENT_PREVIEW_IMAGE_MIN_SCALE;
        scale = imageWidth && imageHeight && viewportWidth && viewportHeight ? Math.min(1, Math.min(viewportWidth / imageWidth, viewportHeight / imageHeight)) : 1;
        fitMode = scale < 1;
        offsetX = viewportWidth ? (viewportWidth - imageWidth * scale) / 2 : 0;
        offsetY = viewportHeight ? (viewportHeight - imageHeight * scale) / 2 : 0;

        updateTransform();
        refs.stage.classList.add('is-ready');
        minimap.setVisible(false);
        applyContentPreviewImageViewerMetadata({
            refs,
            sourceUrl,
            imageMetadata,
            metadataAbort,
            setMetadataAbort: (controller: AbortController | null): void => {
                metadataAbort = controller;
            },
            handleMetadataReady: (): void => refs.info.classList.add('is-ready')
        });
    };

    const handleImageError = (): void => {
        refs.stage.classList.remove('is-ready');
        refs.info.classList.add('is-ready');
        refs.resolution.value.textContent = i18n.t('common.unknown');
        refs.format.value.textContent = i18n.t('common.unknown');
        refs.size.value.textContent = i18n.t('common.unknown');
        refs.zoom.value.textContent = i18n.t('common.unknown');
    };

    const resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(refs.viewport);
    resources.track(resizeObserver, (observer: ResizeObserver) => observer.disconnect());

    resources.addEventListener(refs.image, 'load', handleImageLoad);
    resources.addEventListener(refs.image, 'error', handleImageError);

    const state: ContentPreviewImageViewerState = Object.freeze({
        isReady: (): boolean => Boolean(imageWidth && imageHeight),
        getTransform: (): Readonly<{ scale: number; offsetX: number; offsetY: number; fitMode: boolean }> => Object.freeze({ scale, offsetX, offsetY, fitMode }),
        scheduleMinimapHide: (delayMs: number): void => minimap.scheduleHide(delayMs),
        applyTransform,
        fitToViewport,
        fitToViewportAt,
        centerNative,
        centerNativeAt,
        handleResize,
        handleImageLoad,
        handleImageError,
        dispose: (): void => {
            metadataAbort?.abort();
            metadataAbort = null;
            minimap.dispose();
            resources.cleanup();
        }
    });

    if (refs.image.complete) {
        if (refs.image.naturalWidth > 0) {
            handleImageLoad();
        } else {
            handleImageError();
        }
    }

    return state;
};

export { createContentPreviewImageViewerState };
