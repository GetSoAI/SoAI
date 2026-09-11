/* SoAI - Shared UI media controller [frontend/assets/ts/core/ui/modals/contentpreview/mediaController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ImageViewerGestureActions } from '@core/ui/modals/contentpreview/imageViewerPaging.ts';
import { dom } from '@core/dom/dom.ts';
import { isEditableKeyboardTarget } from '@core/dom/editableTargets.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { requireContentPreviewMediaHost, requireContentPreviewTextHost, requireContentPreviewTextStatsHost, requireContentPreviewTitleHost } from '@core/ui/modals/contentpreview/dom.ts';
import { mountContentPreviewImageViewer, type ContentPreviewImageViewerController } from '@core/ui/modals/contentpreview/imageViewer.ts';
import { createMediaErrorBanner, hideMediaError, showMediaError, wireMediaErrorBannerForIframe, wireMediaErrorBannerForMediaElement } from '@core/ui/modals/contentpreview/mediaErrorBanner.ts';
import { createContentPreviewSourceReferenceStrip } from '@core/ui/modals/contentpreview/sourceReference.ts';
import { hideContentPreviewTextStats } from '@core/ui/modals/contentpreview/textStats.ts';
import { createContentPreviewAudioViewer } from '@core/ui/modals/contentpreview/audioViewer.ts';
import type { ContentPreviewDocumentRequest, ContentPreviewImageNavigationDirection, ContentPreviewMediaRequest, ContentPreviewNonTextRequest } from '@core/ui/modals/contentpreview/types.ts';
import { createContentPreviewVideoViewer } from '@core/ui/modals/contentpreview/videoViewer.ts';

type ContentPreviewMediaController = {
    render: (modalRoot: HTMLElement, request: ContentPreviewNonTextRequest) => void;
    beginImageNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string) => void;
    completeImageNavigation: (modalRoot: HTMLElement, request: ContentPreviewMediaRequest, direction: ContentPreviewImageNavigationDirection) => Promise<boolean>;
    cancelImageNavigation: () => void;
    reset: (modalRoot: HTMLElement) => void;
    dispose: () => void;
};

const isDocumentRequest = (request: ContentPreviewNonTextRequest): request is ContentPreviewDocumentRequest => request.type === 'document' || request.type === 'file';

const isPlainSpaceKey = (event: KeyboardEvent): boolean => {
    return event.key === ' ' && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
};

const isMediaPlaybackKeyboardTarget = (target: EventTarget | null): boolean => {
    if (isEditableKeyboardTarget(target)) {
        return false;
    }
    if (!(target instanceof HTMLElement)) {
        return true;
    }
    if (target instanceof HTMLMediaElement) {
        return false;
    }
    return !target.closest('button, a, input, textarea, select');
};

const toggleMediaPlayback = async (media: HTMLMediaElement): Promise<void> => {
    if (media.paused || media.ended) {
        await media.play();
        return;
    }
    media.pause();
};

const coerceNonEmpty = (value: string, label: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error(`Content preview request ${label} must be non-empty`);
    }
    return trimmed;
};

const releaseMediaSourceUrl = (request: ContentPreviewMediaRequest): void => {
    request.onSourceUrlRelease?.();
};

const renderDocumentPlaceholder = (host: HTMLElement, request: ContentPreviewDocumentRequest): void => {
    const documentRef = dom.getDocument();
    const container = documentRef.createElement('div');
    container.className = 'content-preview-document glass-surface-light glass-surface--rounded';

    const title = documentRef.createElement('h3');
    title.className = 'content-preview-document-title';
    title.textContent = request.title;

    const message = documentRef.createElement('p');
    message.className = 'content-preview-document-message';
    message.textContent = i18n.t('contentPreview.document.downloadToView');
    const sourceStrip = createContentPreviewSourceReferenceStrip(documentRef, request.sourceReference);

    container.appendChild(title);
    container.appendChild(message);
    if (sourceStrip) {
        container.appendChild(sourceStrip);
    }
    host.appendChild(container);
};

const createContentPreviewMediaController = (resources: ResourceTracker, imageActions: Pick<ImageViewerGestureActions, 'requestNavigation' | 'requestClose'>): ContentPreviewMediaController => {
    let activeCleanup: (() => void) | null = null;
    let activeImageViewer: ContentPreviewImageViewerController | null = null;
    let activeImageRequest: ContentPreviewMediaRequest | null = null;

    const disposeActive = (): void => {
        if (!activeCleanup) {
            return;
        }
        const cleanup = activeCleanup;
        activeCleanup = null;
        activeImageViewer = null;
        cleanup();
        activeImageRequest = null;
    };

    const reset = (modalRoot: HTMLElement): void => {
        disposeActive();
        modalRoot.classList.remove('content-preview-modal--media');
        const mediaHost = requireContentPreviewMediaHost(modalRoot);
        mediaHost.textContent = '';
        mediaHost.classList.add('u-hidden');
        mediaHost.setAttribute('aria-hidden', 'true');
        delete mediaHost.dataset['mediaType'];

        const textHost = requireContentPreviewTextHost(modalRoot);
        textHost.classList.remove('u-hidden');
        textHost.setAttribute('aria-hidden', 'false');
    };

    const bindPlaybackShortcut = (modalRoot: HTMLElement, media: HTMLMediaElement): (() => void) => {
        let playbackCommandPending = false;
        return resources.addEventListener(
            modalRoot,
            'keydown',
            async (event: Event): Promise<void> => {
                if (!(event instanceof KeyboardEvent)) {
                    return;
                }
                if (event.defaultPrevented || event.isComposing || !isPlainSpaceKey(event) || !isMediaPlaybackKeyboardTarget(event.target)) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                if (event.repeat || playbackCommandPending) {
                    return;
                }
                playbackCommandPending = true;
                try {
                    await toggleMediaPlayback(media);
                } finally {
                    playbackCommandPending = false;
                }
            },
            { capture: true }
        );
    };

    const render = (modalRoot: HTMLElement, request: ContentPreviewNonTextRequest): void => {
        disposeActive();
        modalRoot.classList.add('content-preview-modal--media');

        requireContentPreviewTitleHost(modalRoot).textContent = request.title;

        const textHost = requireContentPreviewTextHost(modalRoot);
        textHost.textContent = '';
        textHost.classList.remove('prompt-view-text--editing');
        textHost.classList.add('u-hidden');
        textHost.setAttribute('aria-hidden', 'true');
        hideContentPreviewTextStats(requireContentPreviewTextStatsHost(modalRoot));

        const mediaHost = requireContentPreviewMediaHost(modalRoot);
        mediaHost.textContent = '';
        mediaHost.classList.remove('u-hidden');
        mediaHost.setAttribute('aria-hidden', 'false');
        mediaHost.dataset['mediaType'] = request.type;

        if (isDocumentRequest(request)) {
            renderDocumentPlaceholder(mediaHost, request);
            return;
        }

        const mediaRequest: ContentPreviewMediaRequest = request;
        const sourceUrl = coerceNonEmpty(mediaRequest.sourceUrl, 'sourceUrl');
        const errorBanner = createMediaErrorBanner(dom.getDocument());
        hideMediaError(errorBanner);
        mediaHost.appendChild(errorBanner);

        try {
            if (mediaRequest.type === 'image') {
                const imageViewer = mountContentPreviewImageViewer({
                    actions: imageActions,
                    onImageStatus: (status) => (status === 'failed' ? showMediaError(errorBanner) : hideMediaError(errorBanner)),
                    container: mediaHost,
                    title: mediaRequest.title,
                    sourceUrl,
                    imageMetadata: mediaRequest.imageMetadata,
                    imageNavigation: mediaRequest.imageNavigation ?? null,
                    sourceReference: mediaRequest.sourceReference
                });
                activeImageViewer = imageViewer;
                activeImageRequest = mediaRequest;
                activeCleanup = (): void => {
                    imageViewer.dispose();
                    mediaHost.textContent = '';
                    if (activeImageRequest) {
                        releaseMediaSourceUrl(activeImageRequest);
                    }
                };
                return;
            }
            if (mediaRequest.type === 'audio') {
                const audioViewer = createContentPreviewAudioViewer(mediaRequest, sourceUrl);
                const disposeErrorBanner = wireMediaErrorBannerForMediaElement(audioViewer.audio, errorBanner);
                const disposePlaybackShortcut = bindPlaybackShortcut(modalRoot, audioViewer.audio);
                mediaHost.appendChild(audioViewer.viewer);
                activeCleanup = (): void => {
                    disposePlaybackShortcut();
                    disposeErrorBanner();
                    audioViewer.cleanup();
                    mediaHost.textContent = '';
                    releaseMediaSourceUrl(mediaRequest);
                };
                return;
            }
            if (mediaRequest.type === 'video') {
                const videoViewer = createContentPreviewVideoViewer(mediaRequest, sourceUrl);
                const disposeErrorBanner = wireMediaErrorBannerForMediaElement(videoViewer.video, errorBanner);
                const disposePlaybackShortcut = bindPlaybackShortcut(modalRoot, videoViewer.video);
                mediaHost.appendChild(videoViewer.viewer);
                activeCleanup = (): void => {
                    disposePlaybackShortcut();
                    disposeErrorBanner();
                    videoViewer.cleanup();
                    mediaHost.textContent = '';
                    releaseMediaSourceUrl(mediaRequest);
                };
                return;
            }
            if (mediaRequest.type === 'embed') {
                const wrapper = dom.getDocument().createElement('div');
                wrapper.className = 'content-preview-embed';
                const iframe = dom.getDocument().createElement('iframe');
                iframe.src = sourceUrl;
                iframe.title = mediaRequest.title;
                iframe.setAttribute('sandbox', 'allow-forms allow-popups allow-scripts');
                iframe.allow = 'encrypted-media; picture-in-picture';
                iframe.allowFullscreen = true;
                iframe.referrerPolicy = 'no-referrer';
                wrapper.appendChild(iframe);
                const sourceStrip = createContentPreviewSourceReferenceStrip(dom.getDocument(), mediaRequest.sourceReference);
                if (sourceStrip) {
                    wrapper.appendChild(sourceStrip);
                }
                mediaHost.appendChild(wrapper);
                const disposeErrorBanner = wireMediaErrorBannerForIframe(iframe, errorBanner);
                activeCleanup = (): void => {
                    disposeErrorBanner();
                    mediaHost.textContent = '';
                    releaseMediaSourceUrl(mediaRequest);
                };
                return;
            }

            const exhaustiveCheck: never = mediaRequest.type;
            throw new Error(`Unhandled content preview media type: ${String(exhaustiveCheck)}`);
        } catch (error) {
            releaseMediaSourceUrl(mediaRequest);
            throw error;
        }
    };

    resources.track(() => disposeActive());

    return {
        render,
        beginImageNavigation: (direction: ContentPreviewImageNavigationDirection, loadingLabel: string): void => {
            if (!activeImageViewer) {
                throw new Error('Content preview image viewer is unavailable');
            }
            activeImageViewer.beginNavigation(direction, loadingLabel);
        },
        completeImageNavigation: async (modalRoot: HTMLElement, request: ContentPreviewMediaRequest, direction: ContentPreviewImageNavigationDirection): Promise<boolean> => {
            if (request.type !== 'image' || !activeImageViewer) {
                throw new Error('Content preview image navigation requires an active image viewer');
            }
            const committed = await activeImageViewer.completeNavigation(
                {
                    sourceUrl: coerceNonEmpty(request.sourceUrl, 'sourceUrl'),
                    title: request.title,
                    imageMetadata: request.imageMetadata,
                    sourceReference: request.sourceReference,
                    imageNavigation: request.imageNavigation ?? null
                },
                direction
            );
            if (!committed) {
                return false;
            }
            const previousRequest = activeImageRequest;
            activeImageRequest = request;
            if (previousRequest && previousRequest.sourceUrl !== request.sourceUrl) {
                releaseMediaSourceUrl(previousRequest);
            }
            requireContentPreviewTitleHost(modalRoot).textContent = request.title;
            return true;
        },
        cancelImageNavigation: (): void => activeImageViewer?.cancelNavigation(),
        reset,
        dispose: () => disposeActive()
    };
};

export { createContentPreviewMediaController };
export type { ContentPreviewMediaController };
