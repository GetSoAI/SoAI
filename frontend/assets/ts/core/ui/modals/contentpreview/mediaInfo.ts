/* SoAI - Shared content preview media information helpers [frontend/assets/ts/core/ui/modals/contentpreview/mediaInfo.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveUrlPathExtension } from '@core/filePathResolution.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { appendContentPreviewSourceReferenceMetric } from '@core/ui/modals/contentpreview/sourceReference.ts';
import type { ContentPreviewImageMetadata, ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewMediaInfoItem = Readonly<{ value: HTMLElement }>;

type ContentPreviewMediaInfoClasses = Readonly<{
    info: string;
    item: string;
    label: string;
    value: string;
}>;

const CONTENT_PREVIEW_MEDIA_INFO_CLASSES: ContentPreviewMediaInfoClasses = Object.freeze({
    info: 'content-preview-media-info',
    item: 'content-preview-media-info-item',
    label: 'content-preview-media-info-label',
    value: 'content-preview-media-info-value'
});

const createContentPreviewMediaInfoHost = (documentRef: Document): HTMLDListElement => {
    const info = documentRef.createElement('dl');
    info.className = `${CONTENT_PREVIEW_MEDIA_INFO_CLASSES.info} glass-surface-light glass-surface--rounded`;
    return info;
};

const createContentPreviewMediaInfoItem = (documentRef: Document, host: HTMLDListElement, label: string): ContentPreviewMediaInfoItem => {
    const item = documentRef.createElement('div');
    item.className = CONTENT_PREVIEW_MEDIA_INFO_CLASSES.item;

    const title = documentRef.createElement('dt');
    title.className = CONTENT_PREVIEW_MEDIA_INFO_CLASSES.label;
    title.textContent = label;

    const value = documentRef.createElement('dd');
    value.className = CONTENT_PREVIEW_MEDIA_INFO_CLASSES.value;
    value.textContent = i18n.t('common.unknown');

    item.appendChild(title);
    item.appendChild(value);
    host.appendChild(item);

    return Object.freeze({ value });
};

const appendContentPreviewMediaSourceReference = (documentRef: Document, host: HTMLDListElement, sourceReference: ContentPreviewSourceReference | null): void => {
    appendContentPreviewSourceReferenceMetric(documentRef, host, sourceReference, {
        item: CONTENT_PREVIEW_MEDIA_INFO_CLASSES.item,
        label: CONTENT_PREVIEW_MEDIA_INFO_CLASSES.label,
        value: CONTENT_PREVIEW_MEDIA_INFO_CLASSES.value
    });
};

const resolveContentPreviewMediaExtension = (sourceReference: ContentPreviewSourceReference | null, sourceUrl: string): string | null => {
    const sourceReferenceExtension = sourceReference ? resolveUrlPathExtension(sourceReference.value) : null;
    if (sourceReferenceExtension) {
        return sourceReferenceExtension;
    }
    return resolveUrlPathExtension(sourceUrl);
};

const isGenericBinaryContentType = (contentType: string): boolean => {
    return contentType === 'application/octet-stream' || contentType === 'binary/octet-stream';
};

const resolveContentPreviewMediaFormatLabel = (contentType: string | null, sourceReference: ContentPreviewSourceReference | null, sourceUrl: string, expectedPrefix: 'audio/' | 'video/'): string => {
    const normalizedType = contentType ? (contentType.split(';', 1)[0]?.trim() ?? '') : '';
    if (normalizedType) {
        if (normalizedType.startsWith(expectedPrefix)) {
            const subtype = normalizedType.slice(expectedPrefix.length);
            const primary = (subtype.split('+', 1)[0] ?? '').trim();
            if (primary) {
                return primary.toUpperCase();
            }
        }
        const extension = resolveContentPreviewMediaExtension(sourceReference, sourceUrl);
        if (extension && isGenericBinaryContentType(normalizedType)) {
            return extension.toUpperCase();
        }
        return normalizedType;
    }
    const extension = resolveContentPreviewMediaExtension(sourceReference, sourceUrl);
    return extension ? extension.toUpperCase() : i18n.t('common.unknown');
};

const formatContentPreviewMediaDuration = (durationSeconds: number): string => {
    if (!Number.isFinite(durationSeconds) || durationSeconds < 0) {
        return i18n.t('common.unknown');
    }
    const rounded = Math.round(durationSeconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    const seconds = rounded % 60;
    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    return `${minutes}:${String(seconds).padStart(2, '0')}`;
};

const createContentPreviewMediaInfo = (inputArguments: { documentRef: Document; sourceReference: ContentPreviewSourceReference | null; metadata: ContentPreviewImageMetadata | null; sourceUrl: string; expectedPrefix: 'audio/' | 'video/'; includeResolution: boolean }): Readonly<{ info: HTMLDListElement; resolution: ContentPreviewMediaInfoItem | null; duration: ContentPreviewMediaInfoItem }> => {
    const info = createContentPreviewMediaInfoHost(inputArguments.documentRef);
    appendContentPreviewMediaSourceReference(inputArguments.documentRef, info, inputArguments.sourceReference);
    const resolution = inputArguments.includeResolution ? createContentPreviewMediaInfoItem(inputArguments.documentRef, info, i18n.t('contentPreview.mediaInfo.resolution')) : null;
    const format = createContentPreviewMediaInfoItem(inputArguments.documentRef, info, i18n.t('contentPreview.mediaInfo.format'));
    const size = createContentPreviewMediaInfoItem(inputArguments.documentRef, info, i18n.t('contentPreview.mediaInfo.size'));
    const duration = createContentPreviewMediaInfoItem(inputArguments.documentRef, info, i18n.t('contentPreview.mediaInfo.duration'));

    format.value.textContent = resolveContentPreviewMediaFormatLabel(inputArguments.metadata?.contentType ?? null, inputArguments.sourceReference, inputArguments.sourceUrl, inputArguments.expectedPrefix);
    size.value.textContent = formatBytes(inputArguments.metadata?.contentLength ?? null);

    return Object.freeze({ info, resolution, duration });
};

export { createContentPreviewMediaInfo, formatContentPreviewMediaDuration };
