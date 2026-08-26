/* SoAI - Shared file explorer browser media classification [frontend/assets/ts/core/fileexplorerbrowser/mediaClassification.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { FileBrowserMediaType } from '@core/fileexplorerbrowser/types.ts';

const normalizeFileBrowserMimeType = (mimeType: string): string => {
    return toTrimmedString(mimeType).split(';', 1)[0]?.trim().toLowerCase() ?? '';
};

const isFileBrowserImagePreviewMimeType = (mimeType: string): boolean => {
    return normalizeFileBrowserMimeType(mimeType).startsWith('image/');
};

const isFileBrowserAudioPreviewMimeType = (mimeType: string): boolean => {
    return normalizeFileBrowserMimeType(mimeType).startsWith('audio/');
};

const isFileBrowserVideoPreviewMimeType = (mimeType: string): boolean => {
    return normalizeFileBrowserMimeType(mimeType).startsWith('video/');
};

const isFileBrowserTextPreviewMimeType = (mimeType: string): boolean => {
    const normalized = normalizeFileBrowserMimeType(mimeType);
    if (!normalized) {
        return false;
    }
    if (normalized.startsWith('text/')) {
        return true;
    }
    return normalized === 'application/json' || normalized === 'application/xml' || normalized === 'application/xhtml+xml' || normalized.endsWith('+json') || normalized.endsWith('+xml') || normalized === 'application/x-yaml' || normalized === 'application/x-ndjson' || normalized === 'application/jsonl';
};

const classifyFileBrowserMimeType = (mimeType: string): FileBrowserMediaType => {
    const normalized = normalizeFileBrowserMimeType(mimeType);
    if (normalized.startsWith('image/') && normalized !== 'image/svg+xml') {
        return 'image';
    }
    if (normalized.startsWith('audio/')) {
        return 'audio';
    }
    if (normalized.startsWith('video/')) {
        return 'video';
    }
    if (isFileBrowserTextPreviewMimeType(normalized)) {
        return 'text';
    }
    if (normalized === 'application/pdf' || normalized === 'application/msword' || normalized === 'application/rtf' || normalized === 'application/vnd.ms-excel' || normalized === 'application/vnd.ms-powerpoint') {
        return 'document';
    }
    if (normalized.startsWith('application/vnd.openxmlformats-officedocument.') || normalized.startsWith('application/vnd.oasis.opendocument.')) {
        return 'document';
    }
    return 'file';
};

export { classifyFileBrowserMimeType, isFileBrowserAudioPreviewMimeType, isFileBrowserImagePreviewMimeType, isFileBrowserTextPreviewMimeType, isFileBrowserVideoPreviewMimeType, normalizeFileBrowserMimeType };
