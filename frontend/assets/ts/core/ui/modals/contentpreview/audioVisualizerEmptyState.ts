/* SoAI - Content preview audio visualizer empty state overlay [frontend/assets/ts/core/ui/modals/contentpreview/audioVisualizerEmptyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';

type AudioVisualizerEmptyState = Readonly<{ overlay: HTMLDivElement; dispose: () => void }>;

type AudioVisualizerEmptyStateArguments = Readonly<{ documentRef: Document; media: HTMLMediaElement }>;

const createAudioVisualizerEmptyState = ({ documentRef, media }: AudioVisualizerEmptyStateArguments): AudioVisualizerEmptyState => {
    const overlay = documentRef.createElement('div');
    overlay.className = 'content-preview-audio-empty';

    const message = documentRef.createElement('p');
    message.className = 'content-preview-audio-empty-text';
    message.textContent = i18n.t('contentPreview.visualizer.pressPlay');

    const playButton = documentRef.createElement('button');
    playButton.type = 'button';
    playButton.className = 'ui-button ui-variant-neutral content-preview-audio-empty-play';
    playButton.appendChild(createIconSlot(documentRef, getIconSync('play'), { className: 'ui-icon' }));
    const label = documentRef.createElement('span');
    label.textContent = i18n.t('contentPreview.visualizer.play');
    playButton.appendChild(label);

    overlay.appendChild(message);
    overlay.appendChild(playButton);

    const hide = (): void => {
        overlay.classList.add('u-hidden');
        overlay.setAttribute('aria-hidden', 'true');
    };

    const onPlayClick = (): void => {
        void media.play().catch((error) => {
            errorHandler.warn('ContentPreviewAudio', 'Failed to start playback from empty state', ensureError(error));
        });
    };

    const onPlay = (): void => {
        hide();
    };

    playButton.addEventListener('click', onPlayClick);
    media.addEventListener('play', onPlay);

    return Object.freeze({
        overlay,
        dispose: (): void => {
            playButton.removeEventListener('click', onPlayClick);
            media.removeEventListener('play', onPlay);
        }
    });
};

export { createAudioVisualizerEmptyState };
export type { AudioVisualizerEmptyState };
