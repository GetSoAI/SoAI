/* SoAI - FileReader-based image preview extraction [frontend/assets/ts/features/chat/attachments/attachmentImagePreviewReader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isString } from '@core/typeGuards.ts';

const readChatImagePreviewDataUrl = (file: File, logger: ModuleLogger): Promise<string> => {
    const deferred = createDeferred<string>();
    const reader = new FileReader();
    reader.onload = (loadEvent): void => {
        const result = loadEvent.target ? loadEvent.target.result : null;
        if (!isString(result) || !result.trim()) {
            logger('error', 'Failed to read image file', loadEvent);
            deferred.reject(new Error('Image preview read failed.'));
            return;
        }
        deferred.resolve(result);
    };
    reader.onerror = (errorEvent): void => {
        logger('error', 'Failed to read image file', errorEvent);
        deferred.reject(new Error('Image preview read failed.'));
    };
    reader.readAsDataURL(file);
    return deferred.promise;
};

export { readChatImagePreviewDataUrl };
