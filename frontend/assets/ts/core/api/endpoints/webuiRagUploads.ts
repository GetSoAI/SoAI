/* SoAI - Shared API WebUI RAG uploads [frontend/assets/ts/core/api/endpoints/webuiRagUploads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestOptions } from '@core/api/types/request.ts';
import { FILE_TRANSFER_REQUEST_TIMEOUT_MS } from '@core/api/fileTransferTimeout.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

interface RagSingleUploadPayload {
    additionalData: Record<string, string | Blob>;
    options: RequestOptions;
    filenameOverride: string | null;
}

interface RagBatchUploadPayload {
    formData: FormData;
    options: RequestOptions;
}

interface RagBatchUploadOptions extends Omit<RequestOptions, 'query'> {
    query?: {
        attachmentSource: string;
        clientBatchId: string;
    } | null;
}

const readFileRelativePath = (file: File): string => {
    const candidate = isObject(file) ? file : null;
    const rawRelativePath = candidate ? candidate['webkitRelativePath'] : null;
    return isString(rawRelativePath) ? rawRelativePath.trim() : '';
};

const resolveUploadFilenameOverride = (file: File): string | null => {
    const relativePath = readFileRelativePath(file);
    return relativePath && relativePath !== file.name ? relativePath : null;
};

const createRagSingleUploadPayload = (file: File): RagSingleUploadPayload => ({
    additionalData: { 'size_bytes': String(file.size) },
    options: { timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS },
    filenameOverride: resolveUploadFilenameOverride(file)
});

const createRagBatchUploadPayload = (files: readonly File[], options: RagBatchUploadOptions = {}): RagBatchUploadPayload => {
    if (!isArray(files) || files.length <= 0) {
        throw new Error('webui.chat.rag.uploadDocumentsBatch requires at least one file');
    }
    const relativePaths = files.map((file) => {
        const relativePath = readFileRelativePath(file);
        return relativePath || file.name;
    });
    const formData = new FormData();
    formData.append('relative_paths', JSON.stringify(relativePaths));
    formData.append('relative_sizes', JSON.stringify(files.map((file) => file.size)));
    files.forEach((file, index) => {
        const filenameOverride = relativePaths[index] || file.name;
        formData.append('files', file, filenameOverride);
    });
    return {
        formData,
        options: {
            ...options,
            headers: {},
            query:
                options.query === null || options.query === undefined
                    ? null
                    : {
                          'attachment_source': options.query.attachmentSource,
                          'client_batch_id': options.query.clientBatchId
                      },
            timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS
        }
    };
};

export { createRagBatchUploadPayload, createRagSingleUploadPayload };
export type { RagBatchUploadOptions, RagBatchUploadPayload, RagSingleUploadPayload };
