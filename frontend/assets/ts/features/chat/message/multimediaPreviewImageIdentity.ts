/* SoAI - Chat multimedia preview image identity helpers [frontend/assets/ts/features/chat/message/multimediaPreviewImageIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const readPreviewImageSource = (image: HTMLImageElement): string => (image.getAttribute('src') ?? '').trim();

const readPreviewImageOpenSource = (image: HTMLImageElement): string => {
    const openSource = image.dataset['mediaOpenSourceUrl'];
    return (openSource ?? readPreviewImageSource(image)).trim();
};

const previewImagesRepresentSameMedia = (first: HTMLImageElement, second: HTMLImageElement): boolean => {
    const firstSource = readPreviewImageOpenSource(first);
    const secondSource = readPreviewImageOpenSource(second);
    return firstSource !== '' && firstSource === secondSource;
};

export { previewImagesRepresentSameMedia, readPreviewImageOpenSource, readPreviewImageSource };
