/* SoAI - Image viewer scene preparation and transitions [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMaxCssTransitionTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { createAbortError, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';
import { computeFitScale } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import type { ContentPreviewImageNavigationDirection } from '@core/ui/modals/contentpreview/types.ts';

const loadContentPreviewImage = async (sourceUrl: string, title: string, documentRef: Document, signal: AbortSignal): Promise<HTMLImageElement> => {
    const image = documentRef.createElement('img');
    image.className = 'content-preview-image';
    image.alt = title;
    image.decoding = 'async';
    image.loading = 'eager';
    image.draggable = false;
    await withAbortableTimeout(
        (timeoutSignal) =>
            runWithAbortSignalScope(
                [signal, timeoutSignal],
                (loadSignal) =>
                    new Promise<void>((resolve, reject) => {
                        throwIfAborted(loadSignal);
                        const cleanup = (): void => {
                            image.removeEventListener('load', handleLoad);
                            image.removeEventListener('error', handleError);
                            loadSignal.removeEventListener('abort', handleAbort);
                        };
                        const handleLoad = (): void => {
                            cleanup();
                            if (image.naturalWidth > 0 && image.naturalHeight > 0) {
                                resolve();
                            } else {
                                reject(new Error('Preview image has no displayable geometry'));
                            }
                        };
                        const handleError = (): void => {
                            cleanup();
                            reject(new Error('Preview image failed to load'));
                        };
                        const handleAbort = (): void => {
                            cleanup();
                            image.removeAttribute('src');
                            reject(createAbortError());
                        };
                        image.addEventListener('load', handleLoad);
                        image.addEventListener('error', handleError);
                        loadSignal.addEventListener('abort', handleAbort, { once: true });
                        image.src = sourceUrl;
                    })
            ),
        { timeoutMs: 30000, timeoutMessage: 'Preview image load exceeded its deadline' }
    );
    return image;
};

const waitForImageSceneTransition = async (element: HTMLElement, signal: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const transitionMs = resolveMaxCssTransitionTotalMs(element);
    if (transitionMs === 0) {
        return;
    }
    await new Promise<void>((resolve, reject) => {
        const cleanup = (): void => {
            element.removeEventListener('transitionend', finish);
            signal.removeEventListener('abort', abort);
            clearTimeout(timeout);
        };
        const finish = (event?: Event): void => {
            if (event && event.target !== element) {
                return;
            }
            cleanup();
            resolve();
        };
        const abort = (): void => {
            cleanup();
            reject(createAbortError());
        };
        const timeout = setTimeout(finish, transitionMs + 80);
        element.addEventListener('transitionend', finish);
        signal.addEventListener('abort', abort, { once: true });
    });
};

const fitImageScene = (refs: ContentPreviewImageViewerRefs): void => {
    const scale = computeFitScale(refs.image.naturalWidth, refs.image.naturalHeight, refs.viewport.clientWidth, refs.viewport.clientHeight);
    refs.stage.style.width = `${refs.image.naturalWidth}px`;
    refs.stage.style.height = `${refs.image.naturalHeight}px`;
    refs.stage.style.transform = `translate3d(${(refs.viewport.clientWidth - refs.image.naturalWidth * scale) / 2}px, ${(refs.viewport.clientHeight - refs.image.naturalHeight * scale) / 2}px, 0) scale(${scale})`;
};

const prepareImageScene = (refs: ContentPreviewImageViewerRefs, image: HTMLImageElement): ContentPreviewImageViewerRefs => {
    const scene = image.ownerDocument.createElement('div');
    scene.className = 'content-preview-image-scene';
    const stage = image.ownerDocument.createElement('div');
    stage.className = 'content-preview-image-stage is-ready';
    stage.appendChild(image);
    scene.appendChild(stage);
    const prepared = Object.freeze({ ...refs, scene, stage, image });
    fitImageScene(prepared);
    return prepared;
};

const slideImageScene = async (outgoing: ContentPreviewImageViewerRefs, incoming: ContentPreviewImageViewerRefs, direction: ContentPreviewImageNavigationDirection, offset: number, signal: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const track = outgoing.viewer.ownerDocument.createElement('div');
    track.className = `content-preview-image-transition-track content-preview-image-transition-track--${direction}`;
    outgoing.viewport.insertBefore(track, outgoing.scene);
    outgoing.scene.style.transform = '';
    if (direction === 'next') {
        track.append(outgoing.scene, incoming.scene);
    } else {
        track.append(incoming.scene, outgoing.scene);
    }
    track.style.transform = `translate3d(${offset - (direction === 'previous' ? outgoing.viewport.clientWidth : 0)}px, 0, 0)`;
    measureLayoutBox(track);
    track.classList.add('is-sliding', 'is-active');
    track.style.transform = '';
    const resizeObserver = new ResizeObserver(() => fitImageScene(incoming));
    resizeObserver.observe(outgoing.viewport);
    try {
        await waitForImageSceneTransition(track, signal);
    } finally {
        resizeObserver.disconnect();
        if (track.isConnected) {
            outgoing.viewport.insertBefore(outgoing.scene, track);
        }
        track.remove();
    }
};

export { loadContentPreviewImage, prepareImageScene, slideImageScene, waitForImageSceneTransition };
