/* SoAI - Shared chat image load-state lifecycle [frontend/assets/ts/features/chat/attachments/chatImageLoadLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ASSISTANT_ARTICLE_IMAGE_SELECTOR, ATTACHMENT_THUMBNAIL_IMAGE_SELECTOR, CHAT_IMAGE_LIFECYCLE_SELECTOR, CHAT_CONTENT_IMAGE_SELECTOR } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

type ChatImageLoadState = 'error' | 'loaded' | 'loading';

type ChatImageLoadLifecycleArguments = {
    stateAttribute: string;
    resolveStateTarget: (image: HTMLImageElement) => HTMLElement;
    notifyDomChanged: (() => void) | null;
};

const pendingImageLoads = new WeakMap<HTMLImageElement, { source: string | null; cleanup(): void }>();

const CONTENT_IMAGE_LOAD_STATE_ATTRIBUTE = 'data-media-load-state';
const ASSISTANT_ARTICLE_MEDIA_LOAD_STATE_ATTRIBUTE = 'data-image-state';
const ATTACHMENT_MEDIA_LOAD_STATE_ATTRIBUTE = 'data-attachment-image-state';

const resolveImageLoadState = (image: HTMLImageElement): ChatImageLoadState => {
    if (!image.complete) {
        return 'loading';
    }
    return image.naturalWidth > 0 ? 'loaded' : 'error';
};

const syncImageLoadState = (stateTarget: HTMLElement, state: ChatImageLoadState, inputArguments: ChatImageLoadLifecycleArguments): void => {
    let changed = stateTarget.getAttribute(inputArguments.stateAttribute) !== state;
    if (changed) stateTarget.setAttribute(inputArguments.stateAttribute, state);
    if (state === 'loaded' && stateTarget.classList.contains('assistant-image-widget__stage')) {
        const image = dom.resolve('.assistant-image-widget__image', stateTarget);
        if (image instanceof HTMLImageElement && image.naturalWidth > 0 && image.naturalHeight > 0) {
            const aspect = `${String(image.naturalWidth)} / ${String(image.naturalHeight)}`;
            const ratio = String(image.naturalWidth / image.naturalHeight);
            if (stateTarget.style.getPropertyValue('--assistant-image-aspect') !== aspect || stateTarget.style.getPropertyValue('--assistant-image-ratio') !== ratio) {
                stateTarget.style.setProperty('--assistant-image-aspect', aspect);
                stateTarget.style.setProperty('--assistant-image-ratio', ratio);
                changed = true;
            }
        }
    }
    if (changed) inputArguments.notifyDomChanged?.();
};

const prepareChatImageLoadLifecycle = (images: readonly HTMLImageElement[], inputArguments: ChatImageLoadLifecycleArguments): void => {
    for (const image of images) {
        const stateTarget = inputArguments.resolveStateTarget(image);
        const source = image.getAttribute('src');
        const parent = image.parentElement;
        const previous = pendingImageLoads.get(image);
        if (previous !== undefined && previous.source !== source) previous.cleanup();
        const initialState = resolveImageLoadState(image);
        syncImageLoadState(stateTarget, initialState, inputArguments);
        if (initialState !== 'loading' || pendingImageLoads.has(image)) {
            continue;
        }
        const removeListeners = (): void => {
            image.removeEventListener('load', handleLoad);
            image.removeEventListener('error', handleError);
            pendingImageLoads.delete(image);
        };
        const isCurrent = (): boolean => !stateTarget.classList.contains('assistant-image-widget__stage') || (image.isConnected && image.parentElement === parent && image.getAttribute('src') === source && inputArguments.resolveStateTarget(image) === stateTarget);
        const handleLoad = (): void => {
            removeListeners();
            if (!isCurrent()) return;
            syncImageLoadState(stateTarget, image.naturalWidth > 0 ? 'loaded' : 'error', inputArguments);
        };
        const handleError = (): void => {
            removeListeners();
            if (!isCurrent()) return;
            syncImageLoadState(stateTarget, 'error', inputArguments);
        };
        pendingImageLoads.set(image, { source, cleanup: removeListeners });
        image.addEventListener('load', handleLoad);
        image.addEventListener('error', handleError);
        const wiredState = resolveImageLoadState(image);
        if (wiredState !== 'loading') {
            removeListeners();
            syncImageLoadState(stateTarget, wiredState, inputArguments);
        }
    }
};

const resolveAssistantArticleMediaElement = (image: HTMLImageElement): HTMLElement => {
    const mediaElement = image.closest('.assistant-news-widget__media');
    if (!(mediaElement instanceof HTMLElement)) {
        throw new Error('Assistant article image requires a media container');
    }
    return mediaElement;
};

const resolveAttachmentVisualElement = (image: HTMLImageElement): HTMLElement => {
    const visualElement = image.closest('.chat-attachment-visual');
    if (!(visualElement instanceof HTMLElement)) {
        throw new Error('Attachment thumbnail requires a visual container');
    }
    return visualElement;
};

const prepareAttachmentThumbnailLifecycles = (container: HTMLElement): void => {
    const images = dom.resolveAll(ATTACHMENT_THUMBNAIL_IMAGE_SELECTOR, container).filter((node): node is HTMLImageElement => node instanceof HTMLImageElement);
    prepareChatImageLoadLifecycle(images, {
        stateAttribute: ATTACHMENT_MEDIA_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: resolveAttachmentVisualElement,
        notifyDomChanged: null
    });
};

const prepareChatMessageImageLifecycles = (container: HTMLElement, notifyDomChanged: () => void): void => {
    const contentImages: HTMLImageElement[] = [];
    const assistantArticleImages: HTMLImageElement[] = [];
    const imageWidgetImages: HTMLImageElement[] = [];
    const attachmentImages: HTMLImageElement[] = [];
    const images = dom.resolveAll(CHAT_IMAGE_LIFECYCLE_SELECTOR, container).filter((node): node is HTMLImageElement => node instanceof HTMLImageElement);
    for (const image of images) {
        if (image.matches('.assistant-image-widget__image')) imageWidgetImages.push(image);
        else if (image.matches(CHAT_CONTENT_IMAGE_SELECTOR)) contentImages.push(image);
        if (image.matches(ASSISTANT_ARTICLE_IMAGE_SELECTOR)) assistantArticleImages.push(image);
        if (image.matches(ATTACHMENT_THUMBNAIL_IMAGE_SELECTOR)) attachmentImages.push(image);
    }
    prepareChatImageLoadLifecycle(contentImages, {
        stateAttribute: CONTENT_IMAGE_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: (image) => image,
        notifyDomChanged
    });
    prepareChatImageLoadLifecycle(assistantArticleImages, {
        stateAttribute: ASSISTANT_ARTICLE_MEDIA_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: resolveAssistantArticleMediaElement,
        notifyDomChanged
    });
    prepareChatImageLoadLifecycle(imageWidgetImages, {
        stateAttribute: CONTENT_IMAGE_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: (image) => {
            const stage = image.closest('.assistant-image-widget__stage');
            if (!(stage instanceof HTMLElement)) throw new Error('Image widget requires a stage');
            return stage;
        },
        notifyDomChanged
    });
    prepareChatImageLoadLifecycle(attachmentImages, {
        stateAttribute: ATTACHMENT_MEDIA_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: resolveAttachmentVisualElement,
        notifyDomChanged: null
    });
};

export { prepareAttachmentThumbnailLifecycles, prepareChatMessageImageLifecycles };
