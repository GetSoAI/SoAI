/* SoAI - Content preview image viewer [frontend/assets/ts/core/ui/modals/contentpreview/imageViewer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ImageViewerGestureActions } from '@core/ui/modals/contentpreview/imageViewerPaging.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { loadContentPreviewImage, prepareImageScene, slideImageScene, waitForImageSceneTransition } from '@core/ui/modals/contentpreview/imageViewerScene.ts';
import { createContentPreviewImageViewerDom, updateContentPreviewImageNavigation, type ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { createContentPreviewImageViewerGestures } from '@core/ui/modals/contentpreview/imageViewerGestures.ts';
import { createContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerState.ts';
import type { ContentPreviewImageMetadata, ContentPreviewImageNavigation, ContentPreviewImageNavigationDirection, ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type MountArguments = Readonly<{
    actions: Pick<ImageViewerGestureActions, 'requestNavigation' | 'requestClose'>;
    onImageStatus: (status: 'ready' | 'failed') => void;
    container: HTMLElement;
    sourceUrl: string;
    title: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    imageNavigation: ContentPreviewImageNavigation | null;
    sourceReference: ContentPreviewSourceReference | null;
}>;

type ContentPreviewImageNavigationUpdate = Readonly<{
    imageNavigation?: ContentPreviewImageNavigation | null;
    sourceUrl: string;
    title: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    sourceReference: ContentPreviewSourceReference | null;
}>;

type ContentPreviewImageViewerController = Readonly<{
    beginNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string) => void;
    completeNavigation: (update: ContentPreviewImageNavigationUpdate, direction: ContentPreviewImageNavigationDirection) => Promise<boolean>;
    cancelNavigation: () => void;
    dispose: () => void;
}>;

const IMAGE_LOADING_OVERLAY_DELAY_MS = 250;

const setNavigationButtonsDisabled = (refs: ContentPreviewImageViewerRefs, disabled: boolean): void => {
    if (refs.previousButton) {
        refs.previousButton.disabled = disabled;
    }
    if (refs.nextButton) {
        refs.nextButton.disabled = disabled;
    }
};

export const mountContentPreviewImageViewer = ({ actions, onImageStatus, container, sourceUrl, title, imageMetadata, imageNavigation, sourceReference }: MountArguments): ContentPreviewImageViewerController => {
    const url = sourceUrl.trim();
    if (!url) {
        throw new Error('Image viewer sourceUrl must be non-empty');
    }

    let refs = createContentPreviewImageViewerDom(container, url, title, imageNavigation, sourceReference);
    let state = createContentPreviewImageViewerState(refs, url, imageMetadata, onImageStatus);
    let pendingDirection: ContentPreviewImageNavigationDirection | null = null;
    let loadingOverlayTimeout: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;
    let navigationOffset = 0;
    let navigationAbort: AbortController | null = null;
    let currentNavigation = imageNavigation;
    const gestureActions: ImageViewerGestureActions = {
        canNavigate: () => currentNavigation !== null,
        isBlocked: () => disposed || pendingDirection !== null,
        requestClose: actions.requestClose,
        requestNavigation: (direction, offset) => {
            navigationOffset = offset;
            actions.requestNavigation(direction, offset);
        }
    };
    let gestures = createContentPreviewImageViewerGestures({ refs, state, actions: gestureActions });

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
        navigationAbort?.abort();
        navigationAbort = new AbortController();
        gestures.suspend();
        refs.scene.style.transform = `translate3d(${navigationOffset}px, 0, 0)`;
        refs.loadingPath.textContent = loadingPath;
        refs.metadata.classList.add('is-loading');
        setNavigationButtonsDisabled(refs, true);
        loadingOverlayTimeout = setTimeout(() => {
            refs.loadingOverlay.classList.add('is-visible');
        }, IMAGE_LOADING_OVERLAY_DELAY_MS);
    };

    const completeNavigation = async (update: ContentPreviewImageNavigationUpdate, direction: ContentPreviewImageNavigationDirection): Promise<boolean> => {
        if (disposed) {
            return false;
        }
        const controller = navigationAbort;
        if (pendingDirection !== direction || !controller) {
            throw new Error('Image navigation completion does not match the active transition');
        }
        const nextUrl = update.sourceUrl.trim();
        if (!nextUrl) {
            throw new Error('Adjacent image sourceUrl must be non-empty');
        }
        try {
            const incomingImage = await loadContentPreviewImage(nextUrl, update.title, refs.viewer.ownerDocument, controller.signal);
            if (hideLoadingOverlay()) {
                await waitForImageSceneTransition(refs.loadingOverlay, controller.signal);
            }
            const incomingRefs = prepareImageScene(refs, incomingImage);
            await slideImageScene(refs, incomingRefs, direction, navigationOffset, controller.signal);
            if (controller.signal.aborted) {
                return false;
            }
            gestures.dispose();
            state.dispose();
            refs.scene.replaceWith(incomingRefs.scene);
            refs = incomingRefs;
            refs.minimapImage.src = nextUrl;
            refs.viewer.setAttribute('aria-label', update.title);
            if (refs.sourceReference && update.sourceReference) {
                refs.sourceReference.value.textContent = update.sourceReference.value;
            }
            state = createContentPreviewImageViewerState(refs, nextUrl, update.imageMetadata, onImageStatus);
            gestures = createContentPreviewImageViewerGestures({ refs, state, actions: gestureActions });
            restoreMetadata();
            pendingDirection = null;
            navigationOffset = 0;
            navigationAbort = null;
            currentNavigation = update.imageNavigation ?? null;
            updateContentPreviewImageNavigation(refs, currentNavigation);
            setNavigationButtonsDisabled(refs, false);
            return true;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (controller.signal.aborted) {
                return false;
            }
            throw runtimeError;
        }
    };

    const cancelNavigation = (): void => {
        if (pendingDirection === null) {
            return;
        }
        pendingDirection = null;
        navigationAbort?.abort();
        navigationAbort = null;
        navigationOffset = 0;
        gestures.cancel();
        hideLoadingOverlay();
        restoreMetadata();
        setNavigationButtonsDisabled(refs, false);
    };

    const dispose = (): void => {
        disposed = true;
        pendingDirection = null;
        navigationAbort?.abort();
        navigationAbort = null;
        hideLoadingOverlay();
        gestures.dispose();
        state.dispose();
        container.textContent = '';
    };

    return Object.freeze({
        beginNavigation,
        completeNavigation,
        cancelNavigation,
        dispose
    });
};

export type { ContentPreviewImageNavigationUpdate, ContentPreviewImageViewerController };
