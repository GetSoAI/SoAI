/* SoAI - Content preview image viewer metadata [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { resolveUrlPathExtension } from '@core/filePathResolution.ts';
import { i18n } from '@core/i18n/index.ts';
import { headFetch } from '@core/api/headFetch.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ContentPreviewImageMetadata } from '@core/ui/modals/contentpreview/types.ts';

const DATA_IMAGE_PREFIX = 'data:image/';

const resolveContentLength = (rawValue: string | null): number | null => {
    const lengthNumber = rawValue ? Number(rawValue) : null;
    return lengthNumber !== null && isFiniteNumber(lengthNumber) && lengthNumber >= 0 ? lengthNumber : null;
};

const tryParseDataImageMetadata = (url: string): ContentPreviewImageMetadata | null => {
    const trimmed = url.trim();
    if (!trimmed.toLowerCase().startsWith(DATA_IMAGE_PREFIX)) {
        return null;
    }
    const separatorIndex = trimmed.indexOf(',');
    if (separatorIndex < 0) {
        return Object.freeze({ contentType: null, contentLength: null });
    }
    const header = trimmed.slice(5, separatorIndex);
    const payload = trimmed.slice(separatorIndex + 1);
    const headerParts = header.split(';');
    const contentType = headerParts[0]?.trim() || null;
    if (headerParts.includes('base64')) {
        const normalizedPayload = payload.replace(/\s+/g, '');
        const paddingLength = normalizedPayload.endsWith('==') ? 2 : normalizedPayload.endsWith('=') ? 1 : 0;
        const contentLength = normalizedPayload ? Math.max(0, Math.floor((normalizedPayload.length * 3) / 4) - paddingLength) : 0;
        return Object.freeze({ contentType, contentLength });
    }
    try {
        const decodedPayload = decodeURIComponent(payload);
        const contentLength = new TextEncoder().encode(decodedPayload).length;
        return Object.freeze({ contentType, contentLength });
    } catch (error) {
        errorHandler.debug('ContentPreviewImageViewer', 'Failed to decode data image payload metadata', ensureError(error));
        return Object.freeze({ contentType, contentLength: null });
    }
};

const loadContentPreviewImageMetadata = async (url: string, signal: AbortSignal): Promise<ContentPreviewImageMetadata> => {
    const dataImageMetadata = tryParseDataImageMetadata(url);
    if (dataImageMetadata) {
        return dataImageMetadata;
    }
    if (url.trim().toLowerCase().startsWith('blob:')) {
        return Object.freeze({ contentType: null, contentLength: null });
    }
    try {
        const response = await headFetch(url, { signal, credentials: 'same-origin' });
        if (!response.ok) {
            return Object.freeze({ contentType: null, contentLength: null });
        }
        const contentType = response.headers.get('Content-Type');
        const contentLength = resolveContentLength(response.headers.get('Content-Length'));
        return Object.freeze({ contentType, contentLength });
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError)) {
            errorHandler.debug('ContentPreviewImageViewer', 'Failed to load image HEAD metadata', runtimeError);
        }
        return Object.freeze({ contentType: null, contentLength: null });
    }
};

const resolveContentPreviewImageFormatLabel = (contentType: string | null, sourceUrl: string): string => {
    if (contentType) {
        const normalized = contentType.split(';', 1)[0]?.trim().toLowerCase() ?? '';
        if (normalized.startsWith('image/')) {
            const subtype = normalized.slice('image/'.length);
            const primary = (subtype.split('+', 1)[0] ?? '').trim();
            if (primary) {
                return primary.toUpperCase();
            }
        }
        return contentType;
    }

    const ext = resolveUrlPathExtension(sourceUrl);
    return ext ? ext.toUpperCase() : i18n.t('common.unknown');
};

const resolveContentPreviewImageSizeLabel = (contentLength: number | null): string => formatBytes(contentLength);

export { loadContentPreviewImageMetadata, resolveContentPreviewImageFormatLabel, resolveContentPreviewImageSizeLabel };
export type { ContentPreviewImageMetadata };
