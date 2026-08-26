/* SoAI - Chat feature inline multimedia remote link payloads [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { REMOTE_INLINE_MEDIA_PREVIEW_TYPES, type RemoteInlineMediaPreviewType } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { optionalPayloadString, requireAbsentPayloadString, requirePayloadRawString, requirePayloadString, requirePayloadStringEnum } from '@features/chat/message/enhancers/inlineMultimediaPayloadFields.ts';
import { resolveInlineMediaHttpHref } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';

interface RemoteLinkPreviewBase {
    title: string | null;
    description: string | null;
    thumbnailUrl: string | null;
    sourceUrl: string;
}

interface RemoteEmbedPreview extends RemoteLinkPreviewBase {
    type: 'embed';
    previewUrl: string;
    embedUrl: string;
    downloadUrl: null;
    excerptAvailable: false;
}

interface RemoteMediaPreview extends RemoteLinkPreviewBase {
    type: 'image' | 'audio' | 'video';
    previewUrl: string;
    embedUrl: null;
    downloadUrl: string;
    excerptAvailable: false;
}

interface RemoteDownloadPreview extends RemoteLinkPreviewBase {
    type: 'document' | 'file';
    previewUrl: null;
    embedUrl: null;
    downloadUrl: string;
    excerptAvailable: false;
}

interface RemoteTextPreview extends RemoteLinkPreviewBase {
    type: 'text';
    previewUrl: string;
    embedUrl: null;
    downloadUrl: string;
    excerptAvailable: true;
}

interface RemoteBlockedLinkPreview extends RemoteLinkPreviewBase {
    type: 'link';
    previewUrl: null;
    embedUrl: null;
    downloadUrl: null;
    excerptAvailable: false;
}

interface RemotePageLinkPreview extends RemoteLinkPreviewBase {
    type: 'link';
    previewUrl: string;
    embedUrl: null;
    downloadUrl: null;
    excerptAvailable: true;
}

type RemoteLinkPreview = RemoteBlockedLinkPreview | RemoteDownloadPreview | RemoteEmbedPreview | RemoteMediaPreview | RemotePageLinkPreview | RemoteTextPreview;

interface RemoteTextPreviewPayload {
    sourceUrl: string;
    finalUrl: string;
    excerpt: string;
    contentType: string;
}

const requireStringField = (payload: JsonObject, fieldName: string): string => {
    return requirePayloadString(payload, fieldName, 'Remote link preview');
};

const requireHttpUrlField = (payload: JsonObject, fieldName: string): string => {
    return resolveInlineMediaHttpHref(requireStringField(payload, fieldName));
};

const optionalHttpUrlField = (payload: JsonObject, fieldName: string): string | null => {
    const value = optionalPayloadString(payload, fieldName);
    return value === null ? null : resolveInlineMediaHttpHref(value);
};

const requireAbsentStringField = (payload: JsonObject, fieldName: string): null => {
    return requireAbsentPayloadString(payload, fieldName, 'Remote link preview');
};

const parseRemoteLinkPreview = (payload: JsonValue | undefined): RemoteLinkPreview => {
    if (!isJsonObject(payload)) {
        throw new Error('Remote link preview payload is invalid');
    }
    const type: RemoteInlineMediaPreviewType = requirePayloadStringEnum(payload, 'type', 'Remote link preview', REMOTE_INLINE_MEDIA_PREVIEW_TYPES);
    const excerptAvailableValue = payload['excerpt_available'];
    if (!isBoolean(excerptAvailableValue)) {
        throw new Error('Remote link preview missing excerpt_available');
    }
    const base = {
        title: optionalPayloadString(payload, 'title'),
        description: optionalPayloadString(payload, 'description'),
        thumbnailUrl: optionalHttpUrlField(payload, 'thumbnail_url'),
        sourceUrl: requireHttpUrlField(payload, 'source_url')
    };
    if (type === 'embed') {
        if (excerptAvailableValue) {
            throw new Error('Remote embed preview cannot expose excerpt_available');
        }
        return {
            ...base,
            type,
            previewUrl: requireHttpUrlField(payload, 'preview_url'),
            embedUrl: requireHttpUrlField(payload, 'embed_url'),
            downloadUrl: requireAbsentStringField(payload, 'download_url'),
            excerptAvailable: false
        };
    }
    if (type === 'image' || type === 'audio' || type === 'video') {
        if (excerptAvailableValue) {
            throw new Error(`Remote link preview type ${type} cannot expose excerpt_available`);
        }
        return {
            ...base,
            type,
            previewUrl: requireHttpUrlField(payload, 'preview_url'),
            embedUrl: requireAbsentStringField(payload, 'embed_url'),
            downloadUrl: requireHttpUrlField(payload, 'download_url'),
            excerptAvailable: false
        };
    }
    if (type === 'document' || type === 'file') {
        if (excerptAvailableValue) {
            throw new Error(`Remote link preview type ${type} cannot expose excerpt_available`);
        }
        return {
            ...base,
            type,
            previewUrl: requireAbsentStringField(payload, 'preview_url'),
            embedUrl: requireAbsentStringField(payload, 'embed_url'),
            downloadUrl: requireHttpUrlField(payload, 'download_url'),
            excerptAvailable: false
        };
    }
    if (type === 'text') {
        if (!excerptAvailableValue) {
            throw new Error('Remote text preview must expose excerpt_available');
        }
        return {
            ...base,
            type,
            previewUrl: requireHttpUrlField(payload, 'preview_url'),
            embedUrl: requireAbsentStringField(payload, 'embed_url'),
            downloadUrl: requireHttpUrlField(payload, 'download_url'),
            excerptAvailable: true
        };
    }
    if (!excerptAvailableValue) {
        return {
            ...base,
            type: 'link',
            previewUrl: requireAbsentStringField(payload, 'preview_url'),
            embedUrl: requireAbsentStringField(payload, 'embed_url'),
            downloadUrl: requireAbsentStringField(payload, 'download_url'),
            excerptAvailable: false
        };
    }
    return {
        ...base,
        type: 'link',
        previewUrl: requireHttpUrlField(payload, 'preview_url'),
        embedUrl: requireAbsentStringField(payload, 'embed_url'),
        downloadUrl: requireAbsentStringField(payload, 'download_url'),
        excerptAvailable: true
    };
};

const parseRemoteTextPreviewPayload = (payload: JsonValue | undefined): RemoteTextPreviewPayload => {
    if (!isJsonObject(payload)) {
        throw new Error('Remote text preview payload is invalid');
    }
    return {
        sourceUrl: resolveInlineMediaHttpHref(requirePayloadString(payload, 'source_url', 'Remote text preview payload')),
        finalUrl: resolveInlineMediaHttpHref(requirePayloadString(payload, 'final_url', 'Remote text preview payload')),
        excerpt: requirePayloadRawString(payload, 'excerpt', 'Remote text preview payload'),
        contentType: requirePayloadString(payload, 'content_type', 'Remote text preview payload')
    };
};

export { parseRemoteLinkPreview, parseRemoteTextPreviewPayload };
export type { RemoteLinkPreview, RemoteTextPreviewPayload };
