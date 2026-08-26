/* SoAI - Chat feature avatar service [frontend/assets/ts/features/chat/avatar/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isImageMimeType } from '@core/media/mimeTypes.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { AVATAR_MAX_FILE_BYTES, AVATAR_TARGET_SIZE } from '@features/chat/avatar/constants.ts';
import type { AvatarProcessingResult } from '@features/chat/avatar/types.ts';

const validateAvatarFile = (file: File): void => {
    if (!isImageMimeType(file.type)) {
        throw new Error('AVATAR_INVALID_TYPE');
    }
    if (file.size > AVATAR_MAX_FILE_BYTES) {
        throw new Error('AVATAR_TOO_LARGE');
    }
};

const readFileAsDataUrl = (file: File): Promise<string> => {
    const deferred = createDeferred<string>();
    const reader = new FileReader();
    reader.onload = (): void => {
        const result = reader.result;
        if (typeof result !== 'string') {
            deferred.reject(new Error('AVATAR_READ_FAILED'));
            return;
        }
        deferred.resolve(result);
    };
    reader.onerror = (): void => {
        deferred.reject(new Error('AVATAR_READ_FAILED'));
    };
    reader.readAsDataURL(file);
    return deferred.promise;
};

const loadImage = (dataUrl: string): Promise<HTMLImageElement> => {
    const deferred = createDeferred<HTMLImageElement>();
    const image = new Image();
    image.onload = (): void => {
        deferred.resolve(image);
    };
    image.onerror = (): void => {
        deferred.reject(new Error('AVATAR_READ_FAILED'));
    };
    image.src = dataUrl;
    return deferred.promise;
};

const resizeImageToCanvas = (image: HTMLImageElement, targetSize: number): string => {
    const canvas = document.createElement('canvas');
    canvas.width = targetSize;
    canvas.height = targetSize;
    const context = canvas.getContext('2d');
    if (!context) {
        throw new Error('AVATAR_READ_FAILED');
    }

    const sourceWidth = image.naturalWidth;
    const sourceHeight = image.naturalHeight;
    const cropSize = Math.min(sourceWidth, sourceHeight);
    const sourceX = (sourceWidth - cropSize) / 2;
    const sourceY = (sourceHeight - cropSize) / 2;

    context.drawImage(image, sourceX, sourceY, cropSize, cropSize, 0, 0, targetSize, targetSize);
    return canvas.toDataURL('image/png');
};

const processAvatarFile = async (file: File): Promise<AvatarProcessingResult> => {
    validateAvatarFile(file);
    const rawDataUrl = await readFileAsDataUrl(file);
    const image = await loadImage(rawDataUrl);
    const dataUrl = resizeImageToCanvas(image, AVATAR_TARGET_SIZE);
    return { dataUrl };
};

export { processAvatarFile, validateAvatarFile };
