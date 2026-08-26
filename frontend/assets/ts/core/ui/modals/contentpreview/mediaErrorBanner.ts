/* SoAI - Shared UI media error banner [frontend/assets/ts/core/ui/modals/contentpreview/mediaErrorBanner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

const createMediaErrorBanner = (documentRef: Document): HTMLElement => {
    const banner = documentRef.createElement('div');
    banner.className = 'content-preview-media-error u-hidden';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'polite');
    const title = documentRef.createElement('div');
    title.className = 'content-preview-media-error-title';
    title.textContent = i18n.t('contentPreview.errors.loadFailedTitle');
    const message = documentRef.createElement('div');
    message.className = 'content-preview-media-error-message';
    message.textContent = i18n.t('contentPreview.errors.loadFailedMessage');
    banner.appendChild(title);
    banner.appendChild(message);
    return banner;
};

const showMediaError = (banner: HTMLElement): void => {
    banner.classList.remove('u-hidden');
    banner.setAttribute('aria-hidden', 'false');
};

const hideMediaError = (banner: HTMLElement): void => {
    banner.classList.add('u-hidden');
    banner.setAttribute('aria-hidden', 'true');
};

const wireMediaErrorBannerForImage = (image: HTMLImageElement, banner: HTMLElement): (() => void) => {
    const onLoad = (): void => hideMediaError(banner);
    const onError = (): void => showMediaError(banner);
    image.addEventListener('load', onLoad);
    image.addEventListener('error', onError);
    if (image.complete) {
        if (image.naturalWidth > 0) {
            hideMediaError(banner);
        } else {
            showMediaError(banner);
        }
    }
    return (): void => {
        image.removeEventListener('load', onLoad);
        image.removeEventListener('error', onError);
    };
};

const wireMediaErrorBannerForMediaElement = (element: HTMLMediaElement, banner: HTMLElement): (() => void) => {
    const onLoaded = (): void => hideMediaError(banner);
    const onError = (): void => showMediaError(banner);
    element.addEventListener('loadeddata', onLoaded);
    element.addEventListener('error', onError);
    if (element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        hideMediaError(banner);
    }
    return (): void => {
        element.removeEventListener('loadeddata', onLoaded);
        element.removeEventListener('error', onError);
    };
};

const wireMediaErrorBannerForIframe = (iframe: HTMLIFrameElement, banner: HTMLElement): (() => void) => {
    const onLoad = (): void => hideMediaError(banner);
    const onError = (): void => showMediaError(banner);
    iframe.addEventListener('load', onLoad);
    iframe.addEventListener('error', onError);
    return (): void => {
        iframe.removeEventListener('load', onLoad);
        iframe.removeEventListener('error', onError);
    };
};

export { createMediaErrorBanner, hideMediaError, showMediaError, wireMediaErrorBannerForIframe, wireMediaErrorBannerForImage, wireMediaErrorBannerForMediaElement };
