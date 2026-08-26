/* SoAI - Content preview audio visualizer fullscreen control [frontend/assets/ts/core/ui/modals/contentpreview/audioVisualizerFullscreen.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createIconSlot, setIconSlot } from '@core/ui/icons/view.ts';

type AudioVisualizerFullscreenControl = Readonly<{ button: HTMLButtonElement; dispose: () => void }>;

type AudioVisualizerFullscreenArguments = Readonly<{ documentRef: Document; target: HTMLElement; media: HTMLMediaElement }>;

const createAudioVisualizerFullscreenControl = ({ documentRef, target, media }: AudioVisualizerFullscreenArguments): AudioVisualizerFullscreenControl => {
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'ui-icon-button ui-icon-button--titlebar ui-variant-neutral content-preview-audio-fullscreen';
    const iconSlot = createIconSlot(documentRef, getIconSync('fullscreen'), { className: 'ui-icon' });
    button.appendChild(iconSlot);

    const syncVisibility = (): void => {
        const playing = !media.paused && !media.ended;
        button.classList.toggle('u-hidden', !playing);
        button.setAttribute('aria-hidden', playing ? 'false' : 'true');
    };

    const isActive = (): boolean => documentRef.fullscreenElement === target;

    const syncState = (): void => {
        const active = isActive();
        setIconSlot(iconSlot, getIconSync(active ? 'fullscreen-exit' : 'fullscreen'), { className: 'ui-icon' });
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
        button.setAttribute('aria-label', active ? i18n.t('contentPreview.visualizer.fullscreenExit') : i18n.t('contentPreview.visualizer.fullscreenEnter'));
    };

    const toggleFullscreen = async (): Promise<void> => {
        if (documentRef.fullscreenElement) {
            await documentRef.exitFullscreen();
            return;
        }
        await target.requestFullscreen();
    };

    const onClick = (): void => {
        void toggleFullscreen().catch((error) => {
            errorHandler.warn('ContentPreviewAudio', 'Failed to toggle visualizer fullscreen', ensureError(error));
        });
    };

    const onFullscreenChange = (): void => {
        syncState();
    };

    button.addEventListener('click', onClick);
    documentRef.addEventListener('fullscreenchange', onFullscreenChange);
    media.addEventListener('play', syncVisibility);
    media.addEventListener('playing', syncVisibility);
    media.addEventListener('pause', syncVisibility);
    media.addEventListener('ended', syncVisibility);
    syncState();
    syncVisibility();

    return Object.freeze({
        button,
        dispose: (): void => {
            button.removeEventListener('click', onClick);
            documentRef.removeEventListener('fullscreenchange', onFullscreenChange);
            media.removeEventListener('play', syncVisibility);
            media.removeEventListener('playing', syncVisibility);
            media.removeEventListener('pause', syncVisibility);
            media.removeEventListener('ended', syncVisibility);
            if (isActive()) {
                void documentRef.exitFullscreen().catch((error) => {
                    errorHandler.warn('ContentPreviewAudio', 'Failed to exit visualizer fullscreen on dispose', ensureError(error));
                });
            }
        }
    });
};

export { createAudioVisualizerFullscreenControl };
export type { AudioVisualizerFullscreenControl };
