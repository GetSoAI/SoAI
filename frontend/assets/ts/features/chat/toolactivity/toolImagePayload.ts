/* SoAI - Shared tool image payload presentation and signatures [frontend/assets/ts/features/chat/toolactivity/toolImagePayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { hashToolMediaPayloadString } from '@features/chat/toolactivity/toolMediaPayloadHash.ts';

interface ToolImagePayload {
    contentLength: number | null;
    contentType: string;
    imageBase64: string;
}

interface ToolImageDescriptor {
    consumedKeys: string[];
    path: string[];
    payload: ToolImagePayload;
    record: JsonObject;
    pathType: string;
}

interface ToolImageDescriptorOptions {
    toolLeafName?: string;
}

interface OmittedToolImageDescriptor {
    contentType: string;
    path: string[];
    pathType: string;
    record: JsonObject;
    signature: string;
    totalChars: number | null;
}

const TOOL_IMAGE_BASE64_FIELD = 'image_base64';
const TOOL_IMAGE_BASE64_OMITTED_FIELD = 'image_base64_omitted';
const TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD = 'image_base64_total_chars';
const TOOL_IMAGE_SIZE_BYTES_FIELD = 'size_bytes';
const TOOL_IMAGE_CONTENT_TYPE_FIELD = 'content_type';
const TOOL_IMAGE_CONTAINER_FIELDS: readonly string[] = ['screenshot', 'image', 'media', 'preview', 'result'];
const RAW_BROWSER_SCREENSHOT_TOOL_LEAF_NAME = 'browser_screenshot';
const DEFAULT_BROWSER_SCREENSHOT_CONTENT_TYPE = 'image/png';
const SUPPORTED_TOOL_IMAGE_CONTENT_TYPES: readonly string[] = ['image/jpeg', 'image/png', 'image/webp'];

const buildInlineImageDataUrl = (contentType: string, imageBase64: string): string => `data:${contentType};base64,${imageBase64}`;

const resolveImageDownloadName = (contentType: string, fallback: string): string => {
    if (contentType === 'image/jpeg') {
        return replaceDownloadExtension(fallback, 'jpg');
    }
    if (contentType === 'image/png') {
        return replaceDownloadExtension(fallback, 'png');
    }
    if (contentType === 'image/webp') {
        return replaceDownloadExtension(fallback, 'webp');
    }
    return fallback;
};

const replaceDownloadExtension = (fallback: string, extension: string): string => {
    const trimmedFallback = fallback.trim();
    const dotIndex = trimmedFallback.lastIndexOf('.');
    const baseName = dotIndex > 0 ? trimmedFallback.slice(0, dotIndex) : trimmedFallback;
    const normalizedBaseName = baseName || 'soai-image';
    return `${normalizedBaseName}.${extension}`;
};

const shouldInferPngContentType = (options: ToolImageDescriptorOptions): boolean => options.toolLeafName === RAW_BROWSER_SCREENSHOT_TOOL_LEAF_NAME;

const resolvePayloadContentLength = (payload: JsonObject): number | null => {
    const sizeBytes = payload['size_bytes'];
    if (isNonNegativeInteger(sizeBytes)) {
        return sizeBytes;
    }
    const byteSize = payload['byte_size'];
    return isNonNegativeInteger(byteSize) ? byteSize : null;
};

const resolveToolImagePayload = (payload: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): ToolImagePayload | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const contentTypeRaw = payload['content_type'];
    const imageBase64Raw = payload[TOOL_IMAGE_BASE64_FIELD];
    if ((!isString(contentTypeRaw) && !shouldInferPngContentType(options)) || !isString(imageBase64Raw)) {
        return null;
    }
    const contentType = isString(contentTypeRaw) ? contentTypeRaw.trim().toLowerCase() : DEFAULT_BROWSER_SCREENSHOT_CONTENT_TYPE;
    const imageBase64 = imageBase64Raw.trim();
    if (!SUPPORTED_TOOL_IMAGE_CONTENT_TYPES.includes(contentType) || !imageBase64) {
        return null;
    }
    return {
        contentLength: resolvePayloadContentLength(payload),
        contentType,
        imageBase64
    };
};

const resolveOmittedTotalChars = (record: JsonObject): number | null => {
    const totalChars = record[TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD];
    return typeof totalChars === 'number' && Number.isFinite(totalChars) && Number.isInteger(totalChars) && totalChars > 0 ? totalChars : null;
};

const resolveOmittedToolImageSignature = (pathType: string, record: JsonObject, options: ToolImageDescriptorOptions = {}): string | null => {
    if (record[TOOL_IMAGE_BASE64_OMITTED_FIELD] !== true) {
        return null;
    }
    const contentType = isString(record[TOOL_IMAGE_CONTENT_TYPE_FIELD]) ? record[TOOL_IMAGE_CONTENT_TYPE_FIELD].trim().toLowerCase() : shouldInferPngContentType(options) ? DEFAULT_BROWSER_SCREENSHOT_CONTENT_TYPE : '';
    const totalChars = resolveOmittedTotalChars(record);
    const totalCharsText = totalChars === null ? '' : String(totalChars);
    return ['omitted', pathType, contentType, totalCharsText].join(':');
};

const buildToolImagePayloadSignature = (pathType: string, payload: ToolImagePayload): string => {
    return ['inline', pathType, payload.contentType, String(payload.contentLength ?? ''), String(payload.imageBase64.length), hashToolMediaPayloadString(payload.imageBase64)].join(':');
};

const buildPathType = (path: readonly string[]): string => (path.length === 0 ? 'flat' : path.join('.'));

const buildConsumedKeys = (path: readonly string[]): string[] => {
    if (path.length === 0) {
        return [TOOL_IMAGE_CONTENT_TYPE_FIELD, TOOL_IMAGE_BASE64_FIELD, TOOL_IMAGE_BASE64_OMITTED_FIELD, TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD, TOOL_IMAGE_SIZE_BYTES_FIELD, 'byte_size'];
    }
    const first = path[0];
    return first === undefined ? [] : [first];
};

const buildToolImageDescriptor = (path: string[], record: JsonObject, options: ToolImageDescriptorOptions): ToolImageDescriptor | null => {
    const payload = resolveToolImagePayload(record, options);
    if (payload === null) {
        return null;
    }
    const pathType = buildPathType(path);
    return {
        consumedKeys: buildConsumedKeys(path),
        path,
        payload,
        record,
        pathType
    };
};

const buildOmittedToolImageDescriptor = (path: string[], record: JsonObject, options: ToolImageDescriptorOptions): OmittedToolImageDescriptor | null => {
    const pathType = buildPathType(path);
    const signature = resolveOmittedToolImageSignature(pathType, record, options);
    if (signature === null) {
        return null;
    }
    const contentType = isString(record[TOOL_IMAGE_CONTENT_TYPE_FIELD]) ? record[TOOL_IMAGE_CONTENT_TYPE_FIELD].trim().toLowerCase() : shouldInferPngContentType(options) ? DEFAULT_BROWSER_SCREENSHOT_CONTENT_TYPE : '';
    return {
        contentType,
        path,
        pathType,
        record,
        signature,
        totalChars: resolveOmittedTotalChars(record)
    };
};

const findToolImageDescriptor = (payload: JsonValue | undefined, path: string[], options: ToolImageDescriptorOptions): ToolImageDescriptor | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    for (const fieldName of TOOL_IMAGE_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            const nested = findToolImageDescriptor(child, [...path, fieldName], options);
            if (nested !== null) {
                return nested;
            }
        }
    }
    return buildToolImageDescriptor(path, payload, options);
};

const findOmittedToolImageDescriptor = (payload: JsonValue | undefined, path: string[], options: ToolImageDescriptorOptions): OmittedToolImageDescriptor | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    for (const fieldName of TOOL_IMAGE_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            const nested = findOmittedToolImageDescriptor(child, [...path, fieldName], options);
            if (nested !== null) {
                return nested;
            }
        }
    }
    return buildOmittedToolImageDescriptor(path, payload, options);
};

const collectToolImageStateSignatures = (payload: JsonValue | undefined, path: string[] = [], options: ToolImageDescriptorOptions = {}): string[] => {
    if (!isJsonObject(payload)) {
        return [];
    }
    const signatures: string[] = [];
    const inline = buildToolImageDescriptor(path, payload, options);
    if (inline !== null) {
        signatures.push(buildToolImagePayloadSignature(inline.pathType, inline.payload));
    } else {
        const omitted = buildOmittedToolImageDescriptor(path, payload, options);
        if (omitted !== null) {
            signatures.push(omitted.signature);
        }
    }
    for (const fieldName of TOOL_IMAGE_CONTAINER_FIELDS) {
        const child = payload[fieldName];
        if (isJsonObject(child)) {
            signatures.push(...collectToolImageStateSignatures(child, [...path, fieldName], options));
        }
    }
    return signatures;
};

const resolveToolImageDescriptor = (payload: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): ToolImageDescriptor | null => findToolImageDescriptor(payload, [], options);

const resolveOmittedToolImageDescriptor = (payload: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): OmittedToolImageDescriptor | null => findOmittedToolImageDescriptor(payload, [], options);

const resolveToolImageHydrationRank = (payload: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): number => {
    if (resolveToolImageDescriptor(payload, options) !== null) {
        return 2;
    }
    if (resolveOmittedToolImageDescriptor(payload, options) !== null) {
        return 1;
    }
    return 0;
};

const omitToolImageFields = (payload: JsonValue | undefined, consumedKeys: readonly string[]): JsonObject | null => {
    if (!isJsonObject(payload) || consumedKeys.length === 0) {
        return isJsonObject(payload) ? payload : null;
    }
    const filtered: JsonObject = {};
    for (const [key, value] of Object.entries(payload)) {
        if (consumedKeys.includes(key)) {
            continue;
        }
        filtered[key] = value;
    }
    return Object.keys(filtered).length > 0 ? filtered : null;
};

export { TOOL_IMAGE_BASE64_FIELD, TOOL_IMAGE_BASE64_OMITTED_FIELD, TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD, buildInlineImageDataUrl, buildToolImagePayloadSignature, collectToolImageStateSignatures, omitToolImageFields, resolveImageDownloadName, resolveOmittedToolImageDescriptor, resolveToolImageDescriptor, resolveToolImageHydrationRank, resolveToolImagePayload };
export type { OmittedToolImageDescriptor, ToolImageDescriptor, ToolImageDescriptorOptions, ToolImagePayload };
