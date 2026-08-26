/* SoAI - Content preview audio viewer [frontend/assets/ts/core/ui/modals/contentpreview/audioViewer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { createAudioOscilloscope } from '@core/media/audioOscilloscope.ts';
import { createContentPreviewMediaInfo, formatContentPreviewMediaDuration } from '@core/ui/modals/contentpreview/mediaInfo.ts';
import { createAudioVisualizerEmptyState } from '@core/ui/modals/contentpreview/audioVisualizerEmptyState.ts';
import { createAudioVisualizerFullscreenControl } from '@core/ui/modals/contentpreview/audioVisualizerFullscreen.ts';
import type { ContentPreviewMediaRequest } from '@core/ui/modals/contentpreview/types.ts';

const createAudioVisualizerStatus = (documentRef: Document): HTMLDivElement => {
    const status = documentRef.createElement('div');
    status.className = 'content-preview-audio-visualizer-status u-hidden';
    status.setAttribute('aria-live', 'polite');
    status.setAttribute('aria-hidden', 'true');
    return status;
};

const setVisualizerUnavailable = (status: HTMLElement): void => {
    status.textContent = i18n.t('contentPreview.visualizer.unavailable');
    status.classList.remove('u-hidden');
    status.setAttribute('aria-hidden', 'false');
};

const hideVisualizerStatus = (status: HTMLElement): void => {
    status.textContent = '';
    status.classList.add('u-hidden');
    status.setAttribute('aria-hidden', 'true');
};

const stopAudioElement = (audio: HTMLAudioElement): void => {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
};

const createContentPreviewAudioViewer = (request: ContentPreviewMediaRequest, sourceUrl: string): Readonly<{ viewer: HTMLDivElement; audio: HTMLAudioElement; cleanup: () => void }> => {
    const documentRef = dom.getDocument();
    const viewer = documentRef.createElement('div');
    viewer.className = 'content-preview-media-viewer content-preview-audio-viewer';

    const visualizer = documentRef.createElement('div');
    visualizer.className = 'content-preview-audio-visualizer glass-surface-darker';
    visualizer.tabIndex = 0;
    visualizer.setAttribute('role', 'group');
    visualizer.setAttribute('aria-label', i18n.t('contentPreview.visualizer.surface'));

    const canvas = documentRef.createElement('canvas');
    canvas.className = 'content-preview-audio-oscilloscope';
    canvas.setAttribute('aria-hidden', 'true');

    const status = createAudioVisualizerStatus(documentRef);
    visualizer.appendChild(canvas);
    visualizer.appendChild(status);

    const audio = documentRef.createElement('audio');
    audio.className = 'content-preview-audio-element';
    audio.controls = true;
    audio.preload = 'metadata';
    audio.src = sourceUrl;

    const mediaInfo = createContentPreviewMediaInfo({
        documentRef,
        sourceReference: request.sourceReference,
        metadata: request.imageMetadata,
        sourceUrl,
        expectedPrefix: 'audio/',
        includeResolution: false
    });

    const updateAudioMetadata = (): void => {
        mediaInfo.duration.value.textContent = formatContentPreviewMediaDuration(audio.duration);
        mediaInfo.info.classList.add('is-ready');
    };

    const onAudioError = (): void => {
        mediaInfo.duration.value.textContent = i18n.t('common.unknown');
        mediaInfo.info.classList.add('is-ready');
    };

    audio.addEventListener('loadedmetadata', updateAudioMetadata);
    audio.addEventListener('error', onAudioError);
    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) {
        updateAudioMetadata();
    }

    const oscilloscope = createAudioOscilloscope({
        media: audio,
        canvas,
        onStateChange: (state): void => {
            if (state === 'unavailable') {
                setVisualizerUnavailable(status);
                return;
            }
            hideVisualizerStatus(status);
        }
    });

    const emptyState = createAudioVisualizerEmptyState({ documentRef, media: audio });
    const fullscreen = createAudioVisualizerFullscreenControl({ documentRef, target: visualizer, media: audio });
    visualizer.appendChild(emptyState.overlay);
    visualizer.appendChild(fullscreen.button);

    const cycleVisualization = (event: Event): void => {
        if (event.target instanceof Element && event.target.closest('button')) {
            return;
        }
        if (audio.paused || audio.ended) {
            return;
        }
        oscilloscope.cycleMode();
    };

    visualizer.addEventListener('click', cycleVisualization);

    viewer.appendChild(visualizer);
    viewer.appendChild(audio);
    viewer.appendChild(mediaInfo.info);

    return Object.freeze({
        viewer,
        audio,
        cleanup: (): void => {
            oscilloscope.dispose();
            audio.removeEventListener('loadedmetadata', updateAudioMetadata);
            audio.removeEventListener('error', onAudioError);
            visualizer.removeEventListener('click', cycleVisualization);
            fullscreen.dispose();
            emptyState.dispose();
            stopAudioElement(audio);
        }
    });
};

export { createContentPreviewAudioViewer };
