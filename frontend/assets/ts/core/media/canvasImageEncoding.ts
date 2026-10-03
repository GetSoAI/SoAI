/* SoAI - Canvas image encoding [frontend/assets/ts/core/media/canvasImageEncoding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';

const encodeCanvasImage = (canvas: HTMLCanvasElement, mimeType: string, quality?: number): Promise<Blob> => {
    const deferred = createDeferred<Blob>();
    if (typeof canvas.toBlob !== 'function') {
        deferred.reject(new Error('Canvas image encoding is unavailable'));
        return deferred.promise;
    }
    canvas.toBlob(
        (blob) => {
            if (blob === null) {
                deferred.reject(new Error('Canvas produced an empty image'));
                return;
            }
            deferred.resolve(blob);
        },
        mimeType,
        quality
    );
    return deferred.promise;
};

export { encodeCanvasImage };
