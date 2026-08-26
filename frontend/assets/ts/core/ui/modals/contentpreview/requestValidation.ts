/* SoAI - Content preview open request validation [frontend/assets/ts/core/ui/modals/contentpreview/requestValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { normalizeContentPreviewSourceReference } from '@core/ui/modals/contentpreview/sourceReference.ts';
import { normalizeContentPreviewTextBaseline } from '@core/ui/modals/contentpreview/textBaseline.ts';
import type { ContentPreviewDocumentRequest, ContentPreviewImageMetadata, ContentPreviewMediaRequest, ContentPreviewOpenRequest, ContentPreviewSourceReference, ContentPreviewTextBaseline, ContentPreviewTextRequest } from '@core/ui/modals/contentpreview/types.ts';

const requireContentPreviewNonEmpty = (value: string, label: string): string => {
    const trimmed = toTrimmedString(value);
    if (!trimmed) {
        throw new Error(`Content preview request ${label} must be non-empty`);
    }
    return trimmed;
};

const normalizeOptionalContentPreviewText = (value: string | null): string | null => {
    if (value === null) {
        return null;
    }
    return toTrimmedString(value) || null;
};

const normalizeOptionalContentPreviewOpenUrl = (value: string | null, label: string): string | null => {
    if (value === null) {
        return null;
    }
    const trimmed = toTrimmedString(value);
    if (!trimmed) {
        throw new Error(`Content preview request ${label} must be non-empty when provided`);
    }
    return trimmed;
};

const normalizeRequestSourceReference = (sourceReference: ContentPreviewSourceReference | null): ContentPreviewSourceReference | null => normalizeContentPreviewSourceReference(sourceReference);

const normalizeRequestTextBaseline = (baseline: ContentPreviewTextBaseline): ContentPreviewTextBaseline => {
    const normalized = normalizeContentPreviewTextBaseline(baseline);
    return Object.freeze({
        ...normalized,
        title: requireContentPreviewNonEmpty(normalized.title, 'title')
    });
};

const normalizeImageMetadata = (metadata: ContentPreviewImageMetadata | null): ContentPreviewImageMetadata | null => {
    if (metadata === null) {
        return null;
    }
    const contentType = toTrimmedString(metadata.contentType ?? '') || null;
    const contentLength = metadata.contentLength;
    if (contentLength !== null && (!Number.isFinite(contentLength) || contentLength < 0)) {
        throw new Error('Content preview request image metadata contentLength must be a non-negative number');
    }
    return Object.freeze({
        contentType,
        contentLength: contentLength === null ? null : Math.trunc(contentLength)
    });
};

const normalizeTextRequest = (request: ContentPreviewTextRequest): ContentPreviewTextRequest =>
    Object.freeze({
        ...request,
        headerDescription: normalizeOptionalContentPreviewText(request.headerDescription),
        baseline: normalizeRequestTextBaseline(request.baseline),
        sourceReference: normalizeRequestSourceReference(request.sourceReference),
        onSaveComplete: request.onSaveComplete ?? null,
        onRequestAttach: request.onRequestAttach ?? null,
        isUnsavedDraft: request.isUnsavedDraft === true,
        hideActionsWhenEmpty: request.hideActionsWhenEmpty === true,
        openSourceUrl: normalizeOptionalContentPreviewOpenUrl(request.openSourceUrl, 'openSourceUrl')
    });

const normalizeMediaRequest = (request: ContentPreviewMediaRequest): ContentPreviewMediaRequest =>
    Object.freeze({
        ...request,
        headerDescription: normalizeOptionalContentPreviewText(request.headerDescription),
        title: requireContentPreviewNonEmpty(request.title, 'title'),
        sourceUrl: requireContentPreviewNonEmpty(request.sourceUrl, 'sourceUrl'),
        imageMetadata: normalizeImageMetadata(request.imageMetadata),
        sourceReference: normalizeRequestSourceReference(request.sourceReference),
        onRequestAttach: request.onRequestAttach ?? null,
        onSourceUrlRelease: request.onSourceUrlRelease ?? null,
        openSourceUrl: normalizeOptionalContentPreviewOpenUrl(request.openSourceUrl, 'openSourceUrl')
    });

const normalizeDocumentRequest = (request: ContentPreviewDocumentRequest): ContentPreviewDocumentRequest => {
    const sourceReference = normalizeRequestSourceReference(request.sourceReference);
    const openSourceUrl = normalizeOptionalContentPreviewOpenUrl(request.openSourceUrl, 'openSourceUrl');
    if (sourceReference === null && openSourceUrl === null && request.onRequestDownload === null) {
        throw new Error('Content preview document request requires a source reference, open source URL, or download handler');
    }
    return Object.freeze({
        ...request,
        headerDescription: normalizeOptionalContentPreviewText(request.headerDescription),
        title: requireContentPreviewNonEmpty(request.title, 'title'),
        sourceReference,
        onRequestAttach: request.onRequestAttach ?? null,
        openSourceUrl
    });
};

const normalizeContentPreviewOpenRequest = (request: ContentPreviewOpenRequest): ContentPreviewOpenRequest => {
    if (request.type === 'text') {
        return normalizeTextRequest(request);
    }
    if (request.type === 'document' || request.type === 'file') {
        return normalizeDocumentRequest(request);
    }
    if (request.type === 'image' || request.type === 'audio' || request.type === 'video' || request.type === 'embed') {
        return normalizeMediaRequest(request);
    }
    throw new Error('Unsupported content preview request type');
};

export { normalizeContentPreviewOpenRequest };
