/* SoAI - Shared UI video viewer [frontend/assets/ts/core/ui/modals/contentpreview/videoViewer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { createContentPreviewMediaInfo, formatContentPreviewMediaDuration } from '@core/ui/modals/contentpreview/mediaInfo.ts';
import type { ContentPreviewMediaRequest } from '@core/ui/modals/contentpreview/types.ts';

const stopVideoElement = (video: HTMLVideoElement): void => {
    video.pause();
    video.removeAttribute('src');
    video.load();
};

const createContentPreviewVideoViewer = (request: ContentPreviewMediaRequest, sourceUrl: string): Readonly<{ viewer: HTMLDivElement; video: HTMLVideoElement; cleanup: () => void }> => {
    const documentRef = dom.getDocument();
    const viewer = documentRef.createElement('div');
    viewer.className = 'content-preview-media-viewer content-preview-video-viewer';

    const video = documentRef.createElement('video');
    video.className = 'content-preview-video-element';
    video.controls = true;
    video.preload = 'metadata';
    video.src = sourceUrl;

    const mediaInfo = createContentPreviewMediaInfo({
        documentRef,
        sourceReference: request.sourceReference,
        metadata: request.imageMetadata,
        sourceUrl,
        expectedPrefix: 'video/',
        includeResolution: true
    });
    const resolution = mediaInfo.resolution;
    if (!resolution) {
        throw new Error('Content preview video resolution row is missing');
    }

    const updateVideoMetadata = (): void => {
        const width = video.videoWidth;
        const height = video.videoHeight;
        resolution.value.textContent = width > 0 && height > 0 ? `${width}x${height}` : i18n.t('common.unknown');
        mediaInfo.duration.value.textContent = formatContentPreviewMediaDuration(video.duration);
        mediaInfo.info.classList.add('is-ready');
    };

    const onVideoError = (): void => {
        resolution.value.textContent = i18n.t('common.unknown');
        mediaInfo.duration.value.textContent = i18n.t('common.unknown');
        mediaInfo.info.classList.add('is-ready');
    };

    video.addEventListener('loadedmetadata', updateVideoMetadata);
    video.addEventListener('error', onVideoError);
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        updateVideoMetadata();
    }

    viewer.appendChild(video);
    viewer.appendChild(mediaInfo.info);

    return Object.freeze({
        viewer,
        video,
        cleanup: (): void => {
            video.removeEventListener('loadedmetadata', updateVideoMetadata);
            video.removeEventListener('error', onVideoError);
            stopVideoElement(video);
        }
    });
};

export { createContentPreviewVideoViewer };
