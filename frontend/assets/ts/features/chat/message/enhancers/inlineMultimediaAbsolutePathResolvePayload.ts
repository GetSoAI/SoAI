/* SoAI - Chat feature inline multimedia absolute path resolve payload [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaAbsolutePathResolvePayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { RESOLVED_INLINE_MEDIA_PREVIEW_TYPES, type ResolvedInlineMediaPreviewType } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { optionalPayloadString, requirePayloadString, requirePayloadStringEnum } from '@features/chat/message/enhancers/inlineMultimediaPayloadFields.ts';
import { resolveAbsolutePathsPreviewFailure, type InlinePreviewRequestFailure } from '@features/chat/message/enhancers/inlineMultimediaRequestFailure.ts';

interface AbsolutePathsResolveResultOk {
    path: string;
    status: 'ok';
    type: ResolvedInlineMediaPreviewType;
    virtualPath: string;
    mimeType: string | null;
    size: number;
    previewUrl: string | null;
    downloadUrl: string | null;
    openFileExplorerUrl: string;
}

interface AbsolutePathsResolveResultError {
    path: string;
    status: 'error';
    errorCode: string;
    virtualPath: string | null;
    openFileExplorerUrl: string | null;
}

type AbsolutePathsResolveResult = AbsolutePathsResolveResultOk | AbsolutePathsResolveResultError;

const resolveAbsolutePathsResultPreviewFailure = (result: AbsolutePathsResolveResult | null): InlinePreviewRequestFailure => {
    if (!result || result.status !== 'error') {
        return resolveAbsolutePathsPreviewFailure(null);
    }
    return resolveAbsolutePathsPreviewFailure(result.errorCode);
};

const parseAbsolutePathsResolveResult = (payload: JsonValue | undefined): AbsolutePathsResolveResult[] => {
    if (!isJsonObject(payload) || !isJsonArray(payload['results'])) {
        throw new Error('absolute-paths resolve payload is invalid');
    }
    const results: AbsolutePathsResolveResult[] = [];
    for (const entry of payload['results']) {
        if (!isJsonObject(entry) || !isString(entry['status'])) {
            throw new Error('absolute-paths resolve result entry is invalid');
        }
        const path = requirePayloadString(entry, 'path', 'absolute-paths resolve result');
        const status = entry['status'];
        if (status === 'ok') {
            const sizeValue = entry['size'];
            if (!isNonNegativeInteger(sizeValue)) {
                throw new Error('absolute-paths resolve ok result is missing required fields');
            }
            results.push({
                path,
                status: 'ok',
                type: requirePayloadStringEnum(entry, 'type', 'absolute-paths resolve ok result', RESOLVED_INLINE_MEDIA_PREVIEW_TYPES),
                virtualPath: requirePayloadString(entry, 'virtual_path', 'absolute-paths resolve ok result'),
                mimeType: optionalPayloadString(entry, 'mime_type'),
                size: sizeValue,
                previewUrl: optionalPayloadString(entry, 'preview_url'),
                downloadUrl: optionalPayloadString(entry, 'download_url'),
                openFileExplorerUrl: requirePayloadString(entry, 'open_file_explorer_url', 'absolute-paths resolve ok result')
            });
            continue;
        }
        if (status === 'error') {
            results.push({
                path,
                status: 'error',
                errorCode: requirePayloadString(entry, 'error_code', 'absolute-paths resolve error result'),
                virtualPath: optionalPayloadString(entry, 'virtual_path'),
                openFileExplorerUrl: optionalPayloadString(entry, 'open_file_explorer_url')
            });
            continue;
        }
        throw new Error(`absolute-paths resolve result status is unsupported: ${status}`);
    }
    return results;
};

export { parseAbsolutePathsResolveResult, resolveAbsolutePathsResultPreviewFailure };
export type { AbsolutePathsResolveResult, AbsolutePathsResolveResultError, AbsolutePathsResolveResultOk };
