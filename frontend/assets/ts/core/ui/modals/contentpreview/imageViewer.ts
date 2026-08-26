/* SoAI - Content preview image viewer [frontend/assets/ts/core/ui/modals/contentpreview/imageViewer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMaxCssTransitionTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { createContentPreviewImageViewerDom, type ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { createContentPreviewImageViewerGestures } from '@core/ui/modals/contentpreview/imageViewerGestures.ts';
import { createContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerState.ts';
import type { ContentPreviewImageMetadata, ContentPreviewImageNavigation, ContentPreviewImageNavigationDirection, ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type MountArguments = Readonly<{
    container: HTMLElement;
    sourceUrl: string;
    title: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    imageNavigation: ContentPreviewImageNavigation | null;
    sourceReference: ContentPreviewSourceReference | null;
}>;

type ContentPreviewImageNavigationUpdate = Readonly<{
    sourceUrl: string;
    title: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    sourceReference: ContentPreviewSourceReference | null;
}>;

type ContentPreviewImageViewerController = Readonly<{
    beginNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string) => void;
    completeNavigation: (update: ContentPreviewImageNavigationUpdate, direction: ContentPreviewImageNavigationDirection) => Promise<boolean>;
    cancelNavigation: () => void;
    isNavigationPending: () => boolean;
    dispose: () => void;
}>;

const IMAGE_LOADING_OVERLAY_DELAY_MS = 250;

const configureImage = (image: HTMLImageElement, sourceUrl: string, title: string): void => {
    image.className = 'content-preview-image';
    image.alt = title;
    image.decoding = 'async';
    image.loading = 'eager';
    image.draggable = false;
    image.src = sourceUrl;
};

const loadImage = async (sourceUrl: string, title: string, documentRef: Document): Promise<HTMLImageElement> => {
    const image = documentRef.createElement('img');
    await new Promise<void>((resolve, reject) => {
        const handleLoad = (): void => {
            image.removeEventListener('error', handleError);
            resolve();
        };
        const handleError = (): void => {
            image.removeEventListener('load', handleLoad);
            reject(new Error('Adjacent preview image failed to load'));
        };
        image.addEventListener('load', handleLoad, { once: true });
        image.addEventListener('error', handleError, { once: true });
        configureImage(image, sourceUrl, title);
    });
    return image;
};

const waitForTransition = async (element: HTMLElement): Promise<void> => {
    const transitionMs = resolveMaxCssTransitionTotalMs(element);
    if (transitionMs === 0) {
        return;
    }
    await new Promise<void>((resolve) => {
        let settled = false;
        const finish = (event?: Event): void => {
            if (event && event.target !== element) {
                return;
            }
            if (settled) {
                return;
            }
            settled = true;
            element.removeEventListener('transitionend', finish);
            clearTimeout(timeout);
            resolve();
        };
        const timeout = setTimeout(finish, transitionMs + 80);
        element.addEventListener('transitionend', finish);
    });
};

const createIncomingRefs = (refs: ContentPreviewImageViewerRefs, image: HTMLImageElement): ContentPreviewImageViewerRefs => {
    const scene = image.ownerDocument.createElement('div');
    scene.className = 'content-preview-image-scene';
    const stage = image.ownerDocument.createElement('div');
    stage.className = 'content-preview-image-stage';
    stage.appendChild(image);
    scene.appendChild(stage);
    return Object.freeze({ ...refs, scene, stage, image });
};

const createTransitionTrack = (outgoingRefs: ContentPreviewImageViewerRefs, incomingRefs: ContentPreviewImageViewerRefs, direction: ContentPreviewImageNavigationDirection): HTMLDivElement => {
    const track = outgoingRefs.viewer.ownerDocument.createElement('div');
    track.className = `content-preview-image-transition-track content-preview-image-transition-track--${direction}`;
    outgoingRefs.viewport.insertBefore(track, outgoingRefs.scene);
    if (direction === 'next') {
        track.appendChild(outgoingRefs.scene);
        track.appendChild(incomingRefs.scene);
    } else {
        track.appendChild(incomingRefs.scene);
        track.appendChild(outgoingRefs.scene);
    }
    return track;
};

const setNavigationButtonsDisabled = (refs: ContentPreviewImageViewerRefs, disabled: boolean): void => {
    if (refs.previousButton) {
        refs.previousButton.disabled = disabled;
    }
    if (refs.nextButton) {
        refs.nextButton.disabled = disabled;
    }
};

export const mountContentPreviewImageViewer = ({ container, sourceUrl, title, imageMetadata, imageNavigation, sourceReference }: MountArguments): ContentPreviewImageViewerController => {
    const url = sourceUrl.trim();
    if (!url) {
        throw new Error('Image viewer sourceUrl must be non-empty');
    }

    let refs = createContentPreviewImageViewerDom(container, url, title, imageNavigation, sourceReference);
    let state = createContentPreviewImageViewerState(refs, url, imageMetadata);
    let disposeGestures = createContentPreviewImageViewerGestures({ refs, state });
    let pendingDirection: ContentPreviewImageNavigationDirection | null = null;
    let loadingOverlayTimeout: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const hideLoadingOverlay = (): boolean => {
        if (loadingOverlayTimeout !== null) {
            clearTimeout(loadingOverlayTimeout);
            loadingOverlayTimeout = null;
        }
        const wasVisible = refs.loadingOverlay.classList.contains('is-visible');
        refs.loadingOverlay.classList.remove('is-visible');
        return wasVisible;
    };

    const restoreMetadata = (): void => {
        refs.metadata.classList.remove('is-loading');
        refs.loadingPath.textContent = '';
    };

    const beginNavigation = (direction: ContentPreviewImageNavigationDirection, loadingPath: string): void => {
        if (disposed || pendingDirection !== null) {
            return;
        }
        pendingDirection = direction;
        refs.loadingPath.textContent = loadingPath;
        refs.metadata.classList.add('is-loading');
        setNavigationButtonsDisabled(refs, true);
        loadingOverlayTimeout = setTimeout(() => {
            refs.loadingOverlay.classList.add('is-visible');
        }, IMAGE_LOADING_OVERLAY_DELAY_MS);
    };

    const completeNavigation = async (update: ContentPreviewImageNavigationUpdate, direction: ContentPreviewImageNavigationDirection): Promise<boolean> => {
        if (disposed || pendingDirection !== direction) {
            throw new Error('Image navigation completion does not match the active transition');
        }
        const nextUrl = update.sourceUrl.trim();
        if (!nextUrl) {
            throw new Error('Adjacent image sourceUrl must be non-empty');
        }
        const incomingImage = await loadImage(nextUrl, update.title, refs.viewer.ownerDocument);
        if (disposed || pendingDirection !== direction) {
            return false;
        }
        const overlayWasVisible = hideLoadingOverlay();
        if (overlayWasVisible) {
            await waitForTransition(refs.loadingOverlay);
        }
        if (disposed || pendingDirection !== direction) {
            return false;
        }

        const outgoingRefs = refs;
        const incomingRefs = createIncomingRefs(refs, incomingImage);
        const transitionTrack = createTransitionTrack(outgoingRefs, incomingRefs, direction);

        disposeGestures();
        state.dispose();
        refs = incomingRefs;
        refs.minimapImage.src = nextUrl;
        if (refs.sourceReference && update.sourceReference) {
            refs.sourceReference.value.textContent = update.sourceReference.value;
        }
        state = createContentPreviewImageViewerState(refs, nextUrl, update.imageMetadata);
        disposeGestures = createContentPreviewImageViewerGestures({ refs, state });
        restoreMetadata();

        transitionTrack.classList.add('is-sliding');
        await new Promise<void>((resolve) => {
            requestAnimationFrame(() => resolve());
        });
        transitionTrack.classList.add('is-active');
        await waitForTransition(transitionTrack);
        if (disposed || pendingDirection !== direction) {
            transitionTrack.remove();
            return false;
        }
        outgoingRefs.viewport.insertBefore(refs.scene, outgoingRefs.loadingOverlay);
        transitionTrack.remove();
        pendingDirection = null;
        setNavigationButtonsDisabled(refs, false);
        return true;
    };

    const cancelNavigation = (): void => {
        if (pendingDirection === null) {
            return;
        }
        pendingDirection = null;
        hideLoadingOverlay();
        restoreMetadata();
        setNavigationButtonsDisabled(refs, false);
    };

    const dispose = (): void => {
        disposed = true;
        pendingDirection = null;
        hideLoadingOverlay();
        restoreMetadata();
        setNavigationButtonsDisabled(refs, false);
        disposeGestures();
        state.dispose();
        container.textContent = '';
    };

    return Object.freeze({
        beginNavigation,
        completeNavigation,
        cancelNavigation,
        isNavigationPending: (): boolean => pendingDirection !== null,
        dispose
    });
};

export type { ContentPreviewImageNavigationUpdate, ContentPreviewImageViewerController };
