/* SoAI - Chat attach modal dropped payload classification controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDroppedPayloadController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { hasFolderUploadFiles } from '@features/chat/public.ts';

type ChatAttachDroppedPayloadType = 'file' | 'folder';

const dropContainsDirectoryEntry = (event: DragEvent): boolean => {
    const transfer = event.dataTransfer;
    if (transfer === null || transfer.items.length === 0) {
        return false;
    }
    for (const item of Array.from(transfer.items)) {
        const record = isObject(item) ? item : null;
        if (record === null || !isFunction(record['webkitGetAsEntry'])) {
            continue;
        }
        const entry = record['webkitGetAsEntry']();
        if (isObject(entry) && entry['isDirectory'] === true) {
            return true;
        }
    }
    return false;
};

const resolveChatAttachDroppedPayloadType = (event: DragEvent, files: File[]): ChatAttachDroppedPayloadType => {
    return dropContainsDirectoryEntry(event) || hasFolderUploadFiles(files) ? 'folder' : 'file';
};

export { resolveChatAttachDroppedPayloadType };
export type { ChatAttachDroppedPayloadType };
