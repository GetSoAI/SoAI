/* SoAI - Content preview source reference rendering [frontend/assets/ts/core/ui/modals/contentpreview/sourceReference.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolvePathLeaf } from '@core/filePathResolution.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isAbsoluteHttpUrl, resolveHttpUrl } from '@core/security/public.ts';
import type { ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewInfoClassNames = Readonly<{
    item: string;
    label: string;
    value: string;
}>;

type ContentPreviewSourceReferenceMetric = Readonly<{
    label: HTMLElement;
    value: HTMLElement;
}>;

const normalizeContentPreviewSourceReference = (sourceReference: ContentPreviewSourceReference | null | undefined): ContentPreviewSourceReference | null => {
    if (!sourceReference) {
        return null;
    }
    const value = sourceReference.value.trim();
    if (!value) {
        return null;
    }
    if (sourceReference.type === 'url') {
        const resolvedUrl = resolveHttpUrl(value);
        if (resolvedUrl === null) {
            throw new Error('Content preview URL source reference must be a valid absolute HTTP URL');
        }
        return Object.freeze({
            type: 'url',
            value: resolvedUrl
        });
    }
    if (sourceReference.type === 'path') {
        return Object.freeze({
            type: 'path',
            value
        });
    }
    if (sourceReference.type === 'conversation_soai_path') {
        const conversationId = sourceReference.conversationId.trim();
        const rootFingerprint = sourceReference.rootFingerprint.trim();
        if (!conversationId || !rootFingerprint) {
            throw new Error('Content preview conversation SoAI path source reference is incomplete');
        }
        return Object.freeze({
            type: 'conversation_soai_path',
            conversationId,
            rootFingerprint,
            value
        });
    }
    const invalidType: never = sourceReference.type;
    throw new Error(`Content preview source reference type must be path, url, or conversation_soai_path: ${String(invalidType)}`);
};

const resolveUrlLeaf = (url: URL): string => {
    const segments = url.pathname.split('/').filter((segment) => segment.trim().length > 0);
    const leaf = segments.length > 0 ? (segments[segments.length - 1] ?? '') : '';
    if (!leaf) {
        return '';
    }
    return leaf;
};

const resolveUrlDisplayTitle = (value: string): string => {
    const resolvedUrl = resolveHttpUrl(value);
    if (resolvedUrl === null) {
        return value;
    }
    const url = new URL(resolvedUrl);
    const leaf = resolveUrlLeaf(url).trim();
    return leaf ? `${url.hostname}/${leaf}` : url.hostname || value;
};

const resolvePathDisplayTitle = (value: string): string => {
    const leaf = resolvePathLeaf(value);
    return leaf || value;
};

const resolveContentPreviewDisplayTitle = (title: string, sourceReference: ContentPreviewSourceReference | null): string => {
    const normalizedTitle = toTrimmedString(title);
    if (!sourceReference) {
        return normalizedTitle;
    }
    if (normalizedTitle && normalizedTitle !== sourceReference.value && !isAbsoluteHttpUrl(normalizedTitle)) {
        return normalizedTitle;
    }
    if (sourceReference.type === 'url') {
        return resolveUrlDisplayTitle(sourceReference.value);
    }
    return resolvePathDisplayTitle(sourceReference.value);
};

const resolveSourceReferenceLabel = (sourceReference: ContentPreviewSourceReference): string => {
    if (sourceReference.type === 'url') {
        return i18n.t('contentPreview.sourceInfo.url');
    }
    if (sourceReference.type === 'conversation_soai_path') {
        return i18n.t('contentPreview.sourceInfo.conversationPath');
    }
    return i18n.t('contentPreview.sourceInfo.path');
};

const resolveSourceReferenceTitleMetric = (sourceReference: ContentPreviewSourceReference, displayTitle: string | null | undefined): string | null => {
    const normalizedTitle = toTrimmedString(displayTitle);
    if (!normalizedTitle || normalizedTitle === sourceReference.value || isAbsoluteHttpUrl(normalizedTitle)) {
        return null;
    }
    const fallbackTitle = sourceReference.type === 'url' ? resolveUrlDisplayTitle(sourceReference.value) : resolvePathDisplayTitle(sourceReference.value);
    return normalizedTitle === fallbackTitle ? null : normalizedTitle;
};

const appendContentPreviewInfoMetric = (documentRef: Document, host: HTMLDListElement, classNames: ContentPreviewInfoClassNames, labelText: string, valueText: string): ContentPreviewSourceReferenceMetric => {
    const item = documentRef.createElement('div');
    item.className = `${classNames.item} content-preview-source-info-item`;

    const label = documentRef.createElement('dt');
    label.className = `${classNames.label} content-preview-source-info-label`;
    label.textContent = labelText;

    const value = documentRef.createElement('dd');
    value.className = `${classNames.value} content-preview-source-info-value`;
    value.textContent = valueText;

    item.appendChild(label);
    item.appendChild(value);
    host.appendChild(item);
    return Object.freeze({ label, value });
};

const appendContentPreviewSourceReferenceMetric = (documentRef: Document, host: HTMLDListElement, sourceReference: ContentPreviewSourceReference | null, classNames: ContentPreviewInfoClassNames): ContentPreviewSourceReferenceMetric | null => {
    if (!sourceReference) {
        return null;
    }
    return appendContentPreviewInfoMetric(documentRef, host, classNames, resolveSourceReferenceLabel(sourceReference), sourceReference.value);
};

const createContentPreviewSourceReferenceStrip = (documentRef: Document, sourceReference: ContentPreviewSourceReference | null, displayTitle?: string | null): HTMLElement | null => {
    if (!sourceReference) {
        return null;
    }
    const info = documentRef.createElement('dl');
    info.className = 'content-preview-source-info glass-surface-light glass-surface--rounded';
    const classNames = {
        item: 'content-preview-source-info-strip-item',
        label: 'content-preview-source-info-strip-label',
        value: 'content-preview-source-info-strip-value'
    };
    const titleMetric = resolveSourceReferenceTitleMetric(sourceReference, displayTitle);
    if (titleMetric) {
        appendContentPreviewInfoMetric(documentRef, info, classNames, i18n.t('contentPreview.sourceInfo.title'), titleMetric);
    }
    appendContentPreviewSourceReferenceMetric(documentRef, info, sourceReference, classNames);
    return info;
};

export { appendContentPreviewSourceReferenceMetric, createContentPreviewSourceReferenceStrip, normalizeContentPreviewSourceReference, resolveContentPreviewDisplayTitle };
export type { ContentPreviewSourceReferenceMetric };
