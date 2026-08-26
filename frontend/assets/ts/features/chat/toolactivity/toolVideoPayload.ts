/* SoAI - Shared tool video payload presentation and signatures [frontend/assets/ts/features/chat/toolactivity/toolVideoPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { hashToolMediaPayloadString } from '@features/chat/toolactivity/toolMediaPayloadHash.ts';

interface ToolVideoPayload {
    contentLength: number | null;
    contentType: string;
    durationSeconds: number | null;
    height: number | null;
    includesAudio: boolean | null;
    startSeconds: number | null;
    videoBase64: string;
    width: number | null;
}

interface ToolVideoDescriptor {
    consumedKeys: string[];
    path: string[];
    pathType: string;
    payload: ToolVideoPayload;
    record: JsonObject;
}

interface OmittedToolVideoDescriptor {
    contentType: string;
    path: string[];
    pathType: string;
    record: JsonObject;
    signature: string;
    totalChars: number | null;
}

const TOOL_VIDEO_BASE64_FIELD = 'video_base64';
const TOOL_VIDEO_BASE64_OMITTED_FIELD = 'video_base64_omitted';
const TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD = 'video_base64_total_chars';
const TOOL_VIDEO_CONTAINER_FIELDS: readonly string[] = ['video_preview', 'preview', 'video', 'media', 'result'];

const buildInlineVideoDataUrl = (contentType: string, videoBase64: string): string => `data:${contentType};base64,${videoBase64}`;

const resolveOptionalContentLength = (record: JsonObject): number | null => {
    const byteSize = record['byte_size'];
    if (isNonNegativeInteger(byteSize)) {
        return byteSize;
    }
    const sizeBytes = record['size_bytes'];
    return isNonNegativeInteger(sizeBytes) ? sizeBytes : null;
};

const resolveOptionalFiniteNumber = (value: JsonValue | undefined): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);

const resolveOptionalBoolean = (value: JsonValue | undefined): boolean | null => (typeof value === 'boolean' ? value : null);

const resolveToolVideoPayload = (payload: JsonValue | undefined): ToolVideoPayload | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const contentTypeRaw = payload['content_type'];
    const videoBase64Raw = payload[TOOL_VIDEO_BASE64_FIELD];
    if (!isString(contentTypeRaw) || !isString(videoBase64Raw)) {
        return null;
    }
    const contentType = contentTypeRaw.trim().toLowerCase();
    const videoBase64 = videoBase64Raw.trim();
    if (!contentType.startsWith('video/') || !videoBase64) {
        return null;
    }
    return {
        contentLength: resolveOptionalContentLength(payload),
        contentType,
        durationSeconds: resolveOptionalFiniteNumber(payload['duration_seconds']),
        height: resolveOptionalFiniteNumber(payload['height']),
        includesAudio: resolveOptionalBoolean(payload['includes_audio']),
        startSeconds: resolveOptionalFiniteNumber(payload['start_seconds']),
        videoBase64,
        width: resolveOptionalFiniteNumber(payload['width'])
    };
};

const resolveOmittedTotalChars = (record: JsonObject): number | null => {
    const totalChars = record[TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD];
    return typeof totalChars === 'number' && Number.isFinite(totalChars) && Number.isInteger(totalChars) && totalChars > 0 ? totalChars : null;
};

const buildPathType = (path: readonly string[]): string => (path.length === 0 ? 'flat' : path.join('.'));

const buildConsumedKeys = (path: readonly string[]): string[] => {
    if (path.length === 0) {
        return ['content_type', TOOL_VIDEO_BASE64_FIELD, TOOL_VIDEO_BASE64_OMITTED_FIELD, TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD, 'byte_size', 'size_bytes', 'width', 'height', 'duration_seconds', 'start_seconds', 'includes_audio'];
    }
    const first = path[0];
    return first === undefined ? [] : [first];
};

const buildToolVideoPayloadSignature = (pathType: string, payload: ToolVideoPayload): string => {
    return ['inline-video', pathType, payload.contentType, String(payload.contentLength ?? ''), String(payload.videoBase64.length), hashToolMediaPayloadString(payload.videoBase64)].join(':');
};

const resolveOmittedToolVideoSignature = (pathType: string, record: JsonObject): string | null => {
    if (record[TOOL_VIDEO_BASE64_OMITTED_FIELD] !== true) {
        return null;
    }
    const contentType = isString(record['content_type']) ? record['content_type'].trim().toLowerCase() : '';
    const totalChars = resolveOmittedTotalChars(record);
    return ['omitted-video', pathType, contentType, totalChars === null ? '' : String(totalChars)].join(':');
};

const buildToolVideoDescriptor = (path: string[], record: JsonObject): ToolVideoDescriptor | null => {
    const payload = resolveToolVideoPayload(record);
    if (payload === null) {
        return null;
    }
    const pathType = buildPathType(path);
    return {
        consumedKeys: buildConsumedKeys(path),
        path,
        pathType,
        payload,
        record
    };
};

const buildOmittedToolVideoDescriptor = (path: string[], record: JsonObject): OmittedToolVideoDescriptor | null => {
    const pathType = buildPathType(path);
    const signature = resolveOmittedToolVideoSignature(pathType, record);
    if (signature === null) {
        return null;
    }
    const contentType = isString(record['content_type']) ? record['content_type'].trim().toLowerCase() : '';
    return {
        contentType,
        path,
        pathType,
        record,
        signature,
        totalChars: resolveOmittedTotalChars(record)
    };
};

const findToolVideoDescriptor = (payload: JsonValue | undefined, path: string[]): ToolVideoDescriptor | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    for (const fieldName of TOOL_VIDEO_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            const nested = findToolVideoDescriptor(child, [...path, fieldName]);
            if (nested !== null) {
                return nested;
            }
        }
    }
    return buildToolVideoDescriptor(path, payload);
};

const findOmittedToolVideoDescriptor = (payload: JsonValue | undefined, path: string[]): OmittedToolVideoDescriptor | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    for (const fieldName of TOOL_VIDEO_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            const nested = findOmittedToolVideoDescriptor(child, [...path, fieldName]);
            if (nested !== null) {
                return nested;
            }
        }
    }
    return buildOmittedToolVideoDescriptor(path, payload);
};

const collectToolVideoStateSignatures = (payload: JsonValue | undefined, path: string[] = []): string[] => {
    if (!isJsonObject(payload)) {
        return [];
    }
    const signatures: string[] = [];
    const inline = buildToolVideoDescriptor(path, payload);
    if (inline !== null) {
        signatures.push(buildToolVideoPayloadSignature(inline.pathType, inline.payload));
    } else {
        const omitted = buildOmittedToolVideoDescriptor(path, payload);
        if (omitted !== null) {
            signatures.push(omitted.signature);
        }
    }
    for (const fieldName of TOOL_VIDEO_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            signatures.push(...collectToolVideoStateSignatures(child, [...path, fieldName]));
        }
    }
    return signatures;
};

const resolveToolVideoDescriptor = (payload: JsonValue | undefined): ToolVideoDescriptor | null => findToolVideoDescriptor(payload, []);

const resolveOmittedToolVideoDescriptor = (payload: JsonValue | undefined): OmittedToolVideoDescriptor | null => findOmittedToolVideoDescriptor(payload, []);

const resolveToolVideoHydrationRank = (payload: JsonValue | undefined): number => {
    if (resolveToolVideoDescriptor(payload) !== null) {
        return 2;
    }
    if (resolveOmittedToolVideoDescriptor(payload) !== null) {
        return 1;
    }
    return 0;
};

export { TOOL_VIDEO_BASE64_FIELD, TOOL_VIDEO_BASE64_OMITTED_FIELD, TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD, buildInlineVideoDataUrl, collectToolVideoStateSignatures, resolveOmittedToolVideoDescriptor, resolveToolVideoDescriptor, resolveToolVideoHydrationRank };
export type { OmittedToolVideoDescriptor, ToolVideoDescriptor, ToolVideoPayload };
