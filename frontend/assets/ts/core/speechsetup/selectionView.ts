/* SoAI - Speech guidance for selected media inputs [frontend/assets/ts/core/speechsetup/selectionView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { renderSpeechSetupPlaceholder } from '@core/speechsetup/presentation.ts';
import type { SpeechSetupNotePlacement } from '@core/speechsetup/protocols.ts';
import { mountSpeechSetup } from '@core/speechsetup/view.ts';

const createSpeechMediaSelectionView = (anchor: HTMLElement, signal: AbortSignal, placement: SpeechSetupNotePlacement = 'inline'): ((mimeTypes: readonly string[], persisted?: boolean) => void) => {
    let note: HTMLElement | null = null;
    let controller: AbortController | null = null;
    let refresh: (() => void) | null = null;
    const clear = (): void => {
        controller?.abort();
        controller = null;
        refresh = null;
        if (note !== null) removeWithPresence(note);
        note = null;
    };
    signal.addEventListener('abort', clear, { once: true });
    return (mimeTypes, persisted = false): void => {
        const mediaSelected =
            persisted ||
            mimeTypes.some((mimeType) => {
                const type = classifyFileBrowserMimeType(mimeType);
                return type === 'audio' || type === 'video';
            });
        if (signal.aborted || !mediaSelected || anchor.parentElement === null) {
            clear();
            return;
        }
        if (note !== null) {
            const host = dom.resolve('[data-speech-setup]', note);
            if (host instanceof HTMLElement) host.dataset['speechSetup'] = persisted ? 'persisted' : 'advisory';
            refresh?.();
            return;
        }
        note = dom.create('div', { className: 'speech-media-selection', 'data-presence': '' });
        replaceChildrenFromTrustedHtml({ element: note, html: renderSpeechSetupPlaceholder(persisted, placement), context: note });
        insertWithPresence(anchor.parentElement, note, anchor.nextSibling);
        controller = new AbortController();
        refresh = mountSpeechSetup(note, controller.signal);
    };
};

export { createSpeechMediaSelectionView };
