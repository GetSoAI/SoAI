/* SoAI - Chat feature camera vision image optimizer [frontend/assets/ts/features/chat/CameraVisionImageOptimizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';
import { wallClockMs } from '@core/time/clock.ts';

type CameraVisionImageOptimizationOptions = {
    maxPixels: number;
    jpegQuality: number;
    maxOutputBytes: number;
};

const DEFAULT_MAX_PIXELS = 4_000_000;
const DEFAULT_JPEG_QUALITY = 0.85;
const DEFAULT_MAX_OUTPUT_BYTES = 8_000_000;

const normalizeMaxPixels = (value: number): number => {
    if (!Number.isFinite(value)) {
        return DEFAULT_MAX_PIXELS;
    }
    const truncated = Math.trunc(value);
    if (truncated < 1) {
        return DEFAULT_MAX_PIXELS;
    }
    return truncated;
};

const normalizeJpegQuality = (value: number): number => {
    if (!Number.isFinite(value)) {
        return DEFAULT_JPEG_QUALITY;
    }
    if (value <= 0) {
        return 0.01;
    }
    if (value >= 1) {
        return 0.99;
    }
    return value;
};

const normalizeMaxOutputBytes = (value: number): number => {
    if (!Number.isFinite(value)) {
        return DEFAULT_MAX_OUTPUT_BYTES;
    }
    const truncated = Math.trunc(value);
    if (truncated < 1) {
        return DEFAULT_MAX_OUTPUT_BYTES;
    }
    return truncated;
};

const loadImageFromObjectUrl = (file: File): Promise<{ image: HTMLImageElement; objectUrl: string }> => {
    const deferred = createDeferred<HTMLImageElement>();
    const image = new Image();
    const urlRef = globalThis.URL;
    if (!urlRef || typeof urlRef.createObjectURL !== 'function') {
        throw new Error('CHAT_CAMERA_IMAGE_OBJECT_URL_UNAVAILABLE');
    }
    const objectUrl = urlRef.createObjectURL(file);
    const revoke = (): void => {
        if (typeof urlRef.revokeObjectURL === 'function') {
            urlRef.revokeObjectURL(objectUrl);
        }
    };
    image.onload = (): void => {
        const width = image.naturalWidth;
        const height = image.naturalHeight;
        if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
            revoke();
            deferred.reject(new Error('CHAT_CAMERA_IMAGE_DECODE_FAILED'));
            return;
        }
        deferred.resolve(image);
    };
    image.onerror = (): void => {
        revoke();
        deferred.reject(new Error('CHAT_CAMERA_IMAGE_DECODE_FAILED'));
    };
    image.src = objectUrl;
    return deferred.promise.then((resolved) => ({ image: resolved, objectUrl }));
};

const renderJpegBlob = (inputArguments: { image: HTMLImageElement; width: number; height: number; quality: number }): Promise<Blob> => {
    const deferred = createDeferred<Blob>();
    const canvas = document.createElement('canvas');
    canvas.width = inputArguments.width;
    canvas.height = inputArguments.height;
    if (typeof canvas.toBlob !== 'function') {
        deferred.reject(new Error('CHAT_CAMERA_IMAGE_ENCODE_UNSUPPORTED'));
        return deferred.promise;
    }
    const context = canvas.getContext('2d');
    if (!context) {
        deferred.reject(new Error('CHAT_CAMERA_IMAGE_RENDER_FAILED'));
        return deferred.promise;
    }
    context.drawImage(inputArguments.image, 0, 0, inputArguments.width, inputArguments.height);
    canvas.toBlob(
        (blob): void => {
            if (!blob) {
                deferred.reject(new Error('CHAT_CAMERA_IMAGE_ENCODE_FAILED'));
                return;
            }
            deferred.resolve(blob);
        },
        'image/jpeg',
        inputArguments.quality
    );
    return deferred.promise;
};

const encodeWithinMaxBytes = async (inputArguments: { image: HTMLImageElement; width: number; height: number; initialQuality: number; maxBytes: number }): Promise<Blob> => {
    const qualities = [inputArguments.initialQuality, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25].filter((value, index, list) => list.indexOf(value) === index).map((value) => normalizeJpegQuality(value));
    let width = inputArguments.width;
    let height = inputArguments.height;
    let lastBlobSize = 0;
    for (let iteration = 0; iteration < 12; iteration += 1) {
        for (const quality of qualities) {
            const blob = await renderJpegBlob({ image: inputArguments.image, width, height, quality });
            lastBlobSize = blob.size;
            if (blob.size <= inputArguments.maxBytes) {
                return blob;
            }
        }
        if (lastBlobSize <= 0) {
            throw new Error('CHAT_CAMERA_IMAGE_TOO_LARGE');
        }
        const scale = Math.sqrt(inputArguments.maxBytes / lastBlobSize) * 0.92;
        if (!Number.isFinite(scale) || scale <= 0) {
            throw new Error('CHAT_CAMERA_IMAGE_TOO_LARGE');
        }
        const nextWidth = Math.max(1, Math.floor(width * scale));
        const nextHeight = Math.max(1, Math.floor(height * scale));
        if (nextWidth === width && nextHeight === height) {
            throw new Error('CHAT_CAMERA_IMAGE_TOO_LARGE');
        }
        width = nextWidth;
        height = nextHeight;
        if (width * height <= 256) {
            throw new Error('CHAT_CAMERA_IMAGE_TOO_LARGE');
        }
    }
    throw new Error('CHAT_CAMERA_IMAGE_TOO_LARGE');
};

const normalizeJpegFileName = (name: string): string => {
    const trimmed = name.trim();
    if (!trimmed) {
        return 'camera.jpg';
    }
    const lastDot = trimmed.lastIndexOf('.');
    if (lastDot <= 0) {
        return `${trimmed}.jpg`;
    }
    return `${trimmed.slice(0, lastDot)}.jpg`;
};

const computeDownscaledDimensions = (inputArguments: { sourceWidth: number; sourceHeight: number; maxPixels: number }): { width: number; height: number } => {
    const sourcePixels = inputArguments.sourceWidth * inputArguments.sourceHeight;
    if (!Number.isFinite(sourcePixels) || sourcePixels <= 0) {
        throw new Error('CHAT_CAMERA_IMAGE_INVALID_DIMENSIONS');
    }
    if (sourcePixels <= inputArguments.maxPixels) {
        return { width: inputArguments.sourceWidth, height: inputArguments.sourceHeight };
    }
    const scale = Math.sqrt(inputArguments.maxPixels / sourcePixels);
    let width = Math.max(1, Math.floor(inputArguments.sourceWidth * scale));
    let height = Math.max(1, Math.floor(inputArguments.sourceHeight * scale));
    while (width * height > inputArguments.maxPixels) {
        if (width >= height) {
            width = Math.max(1, width - 1);
            continue;
        }
        height = Math.max(1, height - 1);
    }
    return { width, height };
};

const optimizeCameraImageFileForVision = async (file: File, options: Partial<CameraVisionImageOptimizationOptions> = {}): Promise<File> => {
    if (!(file instanceof File)) {
        throw new TypeError('Camera upload requires a File');
    }

    const maxPixels = normalizeMaxPixels(options.maxPixels ?? DEFAULT_MAX_PIXELS);
    const quality = normalizeJpegQuality(options.jpegQuality ?? DEFAULT_JPEG_QUALITY);
    const maxBytes = normalizeMaxOutputBytes(options.maxOutputBytes ?? DEFAULT_MAX_OUTPUT_BYTES);

    const loaded = await loadImageFromObjectUrl(file);
    const sourceWidth = loaded.image.naturalWidth;
    const sourceHeight = loaded.image.naturalHeight;
    try {
        const dims = computeDownscaledDimensions({
            sourceWidth,
            sourceHeight,
            maxPixels
        });
        const blob = await encodeWithinMaxBytes({
            image: loaded.image,
            width: dims.width,
            height: dims.height,
            initialQuality: quality,
            maxBytes
        });
        const outName = normalizeJpegFileName(file.name);
        const lastModified = typeof file.lastModified === 'number' && Number.isFinite(file.lastModified) ? file.lastModified : wallClockMs();
        return new File([blob], outName, { type: 'image/jpeg', lastModified });
    } finally {
        const urlRef = globalThis.URL;
        if (urlRef && typeof urlRef.revokeObjectURL === 'function') {
            urlRef.revokeObjectURL(loaded.objectUrl);
        }
    }
};

export { optimizeCameraImageFileForVision };
export type { CameraVisionImageOptimizationOptions };
