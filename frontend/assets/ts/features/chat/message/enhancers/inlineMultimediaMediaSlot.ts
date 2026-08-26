/* SoAI - Chat feature inline multimedia media slot [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaMediaSlot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { isHTMLAudioElementInOwnDocument, isHTMLElementInOwnDocument, isHTMLImageElementInOwnDocument, isHTMLVideoElementInOwnDocument } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';

type MediaLoadState = 'loading' | 'loaded' | 'error';
type HtmlMediaPreloadMode = 'none' | 'metadata' | 'auto';

interface MediaSlotElements<TMedia extends HTMLElement> {
    slot: HTMLDivElement;
    spinner: HTMLSpanElement;
    error: HTMLDivElement;
    media: TMedia;
}

type MediaSlotLifecycleRegistration = { slot: HTMLElement };

const mediaSlotLifecycleByElement = new WeakMap<HTMLElement, MediaSlotLifecycleRegistration>();

const applyMediaTypeLabel = (slot: HTMLElement, typeLabel: string | null): void => {
    const label = toTrimmedString(typeLabel ?? '');
    if (label) {
        slot.dataset['mediaTypeLabel'] = label;
    }
};

const setInlineMediaSlotLoadState = (slot: HTMLElement, state: MediaLoadState): boolean => {
    const previousState = slot.dataset['mediaLoadState'] ?? '';
    const previousAriaBusy = slot.getAttribute('aria-busy');
    const candidateErrorElement = dom.resolve('.chat-inline-media-card__media-error', slot);
    const errorElement = candidateErrorElement !== null && isHTMLElementInOwnDocument(candidateErrorElement) ? candidateErrorElement : null;
    const previousErrorHidden = errorElement !== null ? errorElement.hidden : null;
    slot.dataset['mediaLoadState'] = state;
    if (state === 'loading') {
        setAriaBusy(slot, true);
        if (errorElement !== null) {
            errorElement.hidden = true;
        }
        const nextErrorHidden = errorElement !== null ? errorElement.hidden : null;
        return previousState !== state || previousAriaBusy !== slot.getAttribute('aria-busy') || previousErrorHidden !== nextErrorHidden;
    }
    setAriaBusy(slot, false);
    if (errorElement !== null) {
        errorElement.hidden = state !== 'error';
    }
    const nextErrorHidden = errorElement !== null ? errorElement.hidden : null;
    return previousState !== state || previousAriaBusy !== slot.getAttribute('aria-busy') || previousErrorHidden !== nextErrorHidden;
};

const updateImageBlurSource = (slot: HTMLElement, image: HTMLImageElement): void => {
    const blurCandidate = dom.resolve('.chat-inline-media-card__image--blurred-bg', slot);
    if (blurCandidate === null || !isHTMLImageElementInOwnDocument(blurCandidate)) return;
    const resolvedSource = image.currentSrc || image.src;
    if (resolvedSource && blurCandidate.src !== resolvedSource) blurCandidate.src = resolvedSource;
};

const registerInlineMediaSlotLifecycle = (slot: HTMLElement, media: HTMLElement): void => {
    const existingRegistration = mediaSlotLifecycleByElement.get(media);
    if (existingRegistration !== undefined) {
        existingRegistration.slot = slot;
        return;
    }
    const registration: MediaSlotLifecycleRegistration = { slot };
    const markLoaded = (): void => {
        if (isHTMLImageElementInOwnDocument(media)) updateImageBlurSource(registration.slot, media);
        setInlineMediaSlotLoadState(registration.slot, 'loaded');
    };
    const markError = (): void => {
        setInlineMediaSlotLoadState(registration.slot, 'error');
    };
    if (isHTMLImageElementInOwnDocument(media)) {
        media.addEventListener('load', markLoaded);
        media.addEventListener('error', markError);
    } else if (isHTMLAudioElementInOwnDocument(media) || isHTMLVideoElementInOwnDocument(media)) {
        media.addEventListener('loadedmetadata', markLoaded);
        media.addEventListener('error', markError);
    } else {
        throw new Error('Inline media slot lifecycle requires an image, audio, or video element');
    }
    mediaSlotLifecycleByElement.set(media, registration);
};

const reconcileLoadedImageSlot = (slot: HTMLElement, image: HTMLImageElement): boolean | null => {
    if (!image.complete || image.naturalWidth <= 0) return null;
    updateImageBlurSource(slot, image);
    return setInlineMediaSlotLoadState(slot, 'loaded');
};

const reconcileInlineMediaSlotLoadState = (slot: HTMLElement, media: HTMLElement): boolean => {
    if (isHTMLImageElementInOwnDocument(media)) {
        const loadedStateChanged = reconcileLoadedImageSlot(slot, media);
        if (loadedStateChanged !== null) return loadedStateChanged;
        if (media.complete && media.naturalWidth <= 0 && Boolean(media.currentSrc || media.src)) return setInlineMediaSlotLoadState(slot, 'error');
        return setInlineMediaSlotLoadState(slot, 'loading');
    }
    if (isHTMLAudioElementInOwnDocument(media)) return setInlineMediaSlotLoadState(slot, media.error === null ? 'loaded' : 'error');
    if (isHTMLVideoElementInOwnDocument(media)) {
        if (media.error !== null) return setInlineMediaSlotLoadState(slot, 'error');
        return setInlineMediaSlotLoadState(slot, media.readyState >= 1 ? 'loaded' : 'loading');
    }
    return false;
};

const createMediaSlot = <TMedia extends HTMLElement>(doc: Document, media: TMedia, options: { errorMessage: string }): MediaSlotElements<TMedia> => {
    const slot = doc.createElement('div');
    slot.className = 'chat-inline-media-card__media';
    setInlineMediaSlotLoadState(slot, 'loading');

    const spinner = doc.createElement('span');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');

    const error = doc.createElement('div');
    error.className = 'chat-inline-media-card__media-error';
    error.textContent = options.errorMessage;
    error.hidden = true;

    slot.appendChild(spinner);
    slot.appendChild(media);
    slot.appendChild(error);

    return { slot, spinner, error, media };
};

const createImageSlot = (
    doc: Document,
    options: {
        alt: string;
        src: string;
        errorMessage: string;
        typeLabel: string | null;
    }
): MediaSlotElements<HTMLImageElement> => {
    const blurImage = doc.createElement('img');
    blurImage.className = 'chat-inline-media-card__image chat-inline-media-card__image--blurred-bg';
    blurImage.alt = '';
    blurImage.decoding = 'async';
    blurImage.loading = 'lazy';
    blurImage.setAttribute('aria-hidden', 'true');

    const img = doc.createElement('img');
    img.className = 'chat-inline-media-card__image';
    img.alt = options.alt;
    img.loading = 'lazy';
    img.decoding = 'async';

    const slot = createMediaSlot(doc, img, { errorMessage: options.errorMessage });
    applyMediaTypeLabel(slot.slot, options.typeLabel);

    slot.slot.classList.add('chat-inline-media-card__media--image-blur-fill');
    slot.slot.insertBefore(blurImage, img);
    registerInlineMediaSlotLifecycle(slot.slot, img);

    img.src = options.src;
    reconcileLoadedImageSlot(slot.slot, img);

    return slot;
};

const createHtmlMediaSlot = <TMedia extends HTMLMediaElement>(
    media: TMedia,
    options: {
        src: string;
        errorMessage: string;
        preload: HtmlMediaPreloadMode;
        controls: boolean;
        initialLoadState: MediaLoadState;
        typeLabel: string | null;
    }
): MediaSlotElements<TMedia> => {
    media.controls = options.controls;
    media.preload = options.preload;

    const slot = createMediaSlot(media.ownerDocument, media, { errorMessage: options.errorMessage });
    applyMediaTypeLabel(slot.slot, options.typeLabel);

    registerInlineMediaSlotLifecycle(slot.slot, media);

    media.src = options.src;

    if (options.initialLoadState === 'loaded') {
        setInlineMediaSlotLoadState(slot.slot, 'loaded');
        return slot;
    }
    if (media.readyState >= 1) {
        setInlineMediaSlotLoadState(slot.slot, 'loaded');
    }

    return slot;
};

const createAudioSlot = (
    doc: Document,
    options: {
        src: string;
        errorMessage: string;
        preload: HtmlMediaPreloadMode;
        controls: boolean;
        typeLabel: string | null;
    }
): MediaSlotElements<HTMLAudioElement> => {
    return createHtmlMediaSlot(doc.createElement('audio'), { ...options, initialLoadState: 'loaded' });
};

const createVideoSlot = (
    doc: Document,
    options: {
        src: string;
        errorMessage: string;
        preload: HtmlMediaPreloadMode;
        controls: boolean;
        typeLabel: string | null;
    }
): MediaSlotElements<HTMLVideoElement> => {
    return createHtmlMediaSlot(doc.createElement('video'), { ...options, initialLoadState: 'loading' });
};

const resolveMediaAltText = (candidate: string, fallback: string): string => {
    const normalized = toTrimmedString(candidate);
    return normalized ? normalized : fallback;
};

export { createAudioSlot, createImageSlot, createVideoSlot, reconcileInlineMediaSlotLoadState, registerInlineMediaSlotLifecycle, resolveMediaAltText, setInlineMediaSlotLoadState };
