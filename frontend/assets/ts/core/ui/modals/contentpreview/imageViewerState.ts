/* SoAI - Content preview image viewer scene state [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { CONTENT_PREVIEW_IMAGE_MAX_SCALE, computeFitScale, resolveViewerOffsets, type Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import { applyContentPreviewImageViewerMetadata } from '@core/ui/modals/contentpreview/imageViewerMetadataState.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { createContentPreviewImageViewerMinimap } from '@core/ui/modals/contentpreview/imageViewerMinimap.ts';
import { computeMinimapProjection } from '@core/ui/modals/contentpreview/imageViewerMinimapProjection.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';
import type { ContentPreviewImageMetadata } from '@core/ui/modals/contentpreview/types.ts';

const createContentPreviewImageViewerState = (refs: ContentPreviewImageViewerRefs, sourceUrl: string, imageMetadata: ContentPreviewImageMetadata | null, onImageStatus: (status: 'ready' | 'failed') => void): ContentPreviewImageViewerState => {
    const resources = new ResourceTracker();
    const minimap = createContentPreviewImageViewerMinimap({ refs, resources });

    let imageWidth = 0;
    let imageHeight = 0;
    let scale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let fitMode = false;
    let previousViewportWidth = 0;
    let previousViewportHeight = 0;
    const resizeListeners = new Set<() => void>();
    const maxScale = CONTENT_PREVIEW_IMAGE_MAX_SCALE;
    let metadataAbort: AbortController | null = null;
    let loadDeadline: number | null = null;
    const clearLoadDeadline = (): void => {
        if (loadDeadline !== null) {
            resources.clearTimeout(loadDeadline);
            loadDeadline = null;
        }
    };

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
        return computeFitScale(imageWidth, imageHeight, viewportWidth, viewportHeight);
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

    const applyTransform = (nextScale: number, nextOffsetX: number, nextOffsetY: number, showMinimap: boolean, elastic = false): boolean => {
        if (![nextScale, nextOffsetX, nextOffsetY].every(Number.isFinite) || nextScale <= 0) {
            throw new Error('Image transform requires finite coordinates and a positive scale');
        }
        const minimum = computeFitScaleValue();
        const clampedScale = clampNumber(nextScale, elastic ? minimum * 0.84 : minimum, elastic ? maxScale * 1.08 : maxScale);
        const clampedOffsets = elastic ? { x: nextOffsetX, y: nextOffsetY } : resolveOffsets(clampedScale, nextOffsetX, nextOffsetY);
        if (clampedScale === scale && clampedOffsets.x === offsetX && clampedOffsets.y === offsetY) {
            return false;
        }
        scale = clampedScale;
        offsetX = clampedOffsets.x;
        offsetY = clampedOffsets.y;
        fitMode = Math.abs(scale / minimum - 1) <= 0.001;
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

    const handleResize = (): void => {
        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        if (!imageWidth || !imageHeight || !viewportWidth || !viewportHeight || (viewportWidth === previousViewportWidth && viewportHeight === previousViewportHeight)) {
            return;
        }
        const centerX = (previousViewportWidth / 2 - offsetX) / scale;
        const centerY = (previousViewportHeight / 2 - offsetY) / scale;
        if (fitMode) {
            fitToViewport(false);
        } else {
            scale = clampNumber(scale, computeFitScaleValue(), maxScale);
            const clamped = resolveOffsets(scale, viewportWidth / 2 - centerX * scale, viewportHeight / 2 - centerY * scale);
            offsetX = clamped.x;
            offsetY = clamped.y;
            fitMode = Math.abs(scale / computeFitScaleValue() - 1) <= 0.001;
            render(false);
        }
        previousViewportWidth = viewportWidth;
        previousViewportHeight = viewportHeight;
        resizeListeners.forEach((listener) => listener());
    };

    const handleImageLoad = (): void => {
        clearLoadDeadline();
        onImageStatus('ready');
        imageWidth = refs.image.naturalWidth;
        imageHeight = refs.image.naturalHeight;
        refs.stage.style.width = `${imageWidth}px`;
        refs.stage.style.height = `${imageHeight}px`;
        refs.resolution.value.textContent = `${imageWidth}x${imageHeight}`;
        configureMinimapSize();

        const viewportWidth = refs.viewport.clientWidth;
        const viewportHeight = refs.viewport.clientHeight;
        previousViewportWidth = viewportWidth;
        previousViewportHeight = viewportHeight;
        scale = imageWidth && imageHeight && viewportWidth && viewportHeight ? computeFitScale(imageWidth, imageHeight, viewportWidth, viewportHeight) : 1;
        fitMode = true;
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
        clearLoadDeadline();
        metadataAbort?.abort();
        metadataAbort = null;
        onImageStatus('failed');
        imageWidth = 0;
        imageHeight = 0;
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
        getGeometry: () => ({ imageWidth, imageHeight, viewportWidth: refs.viewport.clientWidth, viewportHeight: refs.viewport.clientHeight, fitScale: computeFitScaleValue() }),
        subscribeResize: (listener: () => void): (() => void) => {
            resizeListeners.add(listener);
            return () => {
                resizeListeners.delete(listener);
            };
        },
        scheduleMinimapHide: (delayMs: number): void => minimap.scheduleHide(delayMs),
        applyTransform,
        fitToViewport,
        handleResize,
        handleImageLoad,
        handleImageError,
        dispose: (): void => {
            resizeListeners.clear();
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

    if (!refs.image.complete) {
        loadDeadline = resources.setTimeout(() => {
            handleImageError();
            refs.image.removeAttribute('src');
        }, 30000);
    }

    return state;
};

export { createContentPreviewImageViewerState };
