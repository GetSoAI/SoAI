/* SoAI - Chat image load-state lifecycle wiring [frontend/assets/ts/features/chat/message/postrender/chatImageLoadLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ASSISTANT_ARTICLE_IMAGE_SELECTOR, CHAT_IMAGE_LIFECYCLE_SELECTOR, INLINE_TOOL_IMAGE_SELECTOR } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

type ChatImageLoadState = 'error' | 'loaded' | 'loading';

type ChatImageLoadLifecycleArguments = {
    wiredAttribute: string;
    stateAttribute: string;
    resolveStateTarget: (image: HTMLImageElement) => HTMLElement;
    notifyDomChanged: () => void;
};

const INLINE_TOOL_LIFECYCLE_WIRED_ATTRIBUTE = 'data-inline-tool-image-lifecycle-wired';
const INLINE_TOOL_MEDIA_LOAD_STATE_ATTRIBUTE = 'data-media-load-state';
const ASSISTANT_ARTICLE_LIFECYCLE_WIRED_ATTRIBUTE = 'data-news-image-lifecycle-wired';
const ASSISTANT_ARTICLE_MEDIA_LOAD_STATE_ATTRIBUTE = 'data-image-state';

const resolveImageLoadState = (image: HTMLImageElement): ChatImageLoadState => {
    if (!image.complete) {
        return 'loading';
    }
    return image.naturalWidth > 0 ? 'loaded' : 'error';
};

const syncImageLoadState = (image: HTMLImageElement, inputArguments: ChatImageLoadLifecycleArguments): void => {
    const stateTarget = inputArguments.resolveStateTarget(image);
    const nextState = resolveImageLoadState(image);
    if (stateTarget.getAttribute(inputArguments.stateAttribute) === nextState) {
        return;
    }
    stateTarget.setAttribute(inputArguments.stateAttribute, nextState);
    inputArguments.notifyDomChanged();
};

const prepareChatImageLoadLifecycle = (images: readonly HTMLImageElement[], inputArguments: ChatImageLoadLifecycleArguments): void => {
    for (const image of images) {
        syncImageLoadState(image, inputArguments);
        if (image.getAttribute(inputArguments.wiredAttribute) === 'true') {
            continue;
        }
        image.setAttribute(inputArguments.wiredAttribute, 'true');
        const handleLoad = (): void => {
            syncImageLoadState(image, inputArguments);
        };
        const handleError = (): void => {
            syncImageLoadState(image, inputArguments);
        };
        image.addEventListener('load', handleLoad);
        image.addEventListener('error', handleError);
    }
};

const resolveAssistantArticleMediaElement = (image: HTMLImageElement): HTMLElement => {
    const mediaElement = image.closest('.assistant-news-widget__media');
    if (!(mediaElement instanceof HTMLElement)) {
        throw new Error('Assistant article image requires a media container');
    }
    return mediaElement;
};

const prepareChatMessageImageLifecycles = (container: HTMLElement, notifyDomChanged: () => void): void => {
    const inlineToolImages: HTMLImageElement[] = [];
    const assistantArticleImages: HTMLImageElement[] = [];
    const images = dom.resolveAll(CHAT_IMAGE_LIFECYCLE_SELECTOR, container).filter((node): node is HTMLImageElement => node instanceof HTMLImageElement);
    for (const image of images) {
        if (image.matches(INLINE_TOOL_IMAGE_SELECTOR)) {
            inlineToolImages.push(image);
        }
        if (image.matches(ASSISTANT_ARTICLE_IMAGE_SELECTOR)) {
            assistantArticleImages.push(image);
        }
    }
    prepareChatImageLoadLifecycle(inlineToolImages, {
        wiredAttribute: INLINE_TOOL_LIFECYCLE_WIRED_ATTRIBUTE,
        stateAttribute: INLINE_TOOL_MEDIA_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: (image) => image,
        notifyDomChanged
    });
    prepareChatImageLoadLifecycle(assistantArticleImages, {
        wiredAttribute: ASSISTANT_ARTICLE_LIFECYCLE_WIRED_ATTRIBUTE,
        stateAttribute: ASSISTANT_ARTICLE_MEDIA_LOAD_STATE_ATTRIBUTE,
        resolveStateTarget: resolveAssistantArticleMediaElement,
        notifyDomChanged
    });
};

export { prepareChatMessageImageLifecycles };
