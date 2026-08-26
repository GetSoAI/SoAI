/* SoAI - Chat feature inline multimedia file explorer resolution [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaFileExplorerResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildFileExplorerListUrl, buildFileExplorerMetadataUrl, buildFileExplorerReadUrl } from '@core/api/endpoints/fileExplorerPaths.ts';
import { decodeFileExplorerListResponse, decodeFileExplorerMetadataResponse, decodeFileExplorerReadResponse } from '@core/api/contracts/fileExplorerContracts.ts';
import { fetchJson, type JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { mapWithConcurrencyLimit } from '@core/concurrency/mapWithConcurrencyLimit.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { parseFileBrowserListPayload, parseFileBrowserMetadataPayload, parseFileBrowserReadPayload } from '@core/fileexplorerbrowser/payloads.ts';
import type { FileBrowserListPayload, FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import type { ContentPreviewReasonCode } from '@features/chat/contentPreviewContracts.ts';
import { resolveInlinePreviewRequestFailure } from '@features/chat/message/enhancers/inlineMultimediaRequestFailure.ts';

const FOLDER_PREVIEW_ENTRY_LIMIT = 5;

interface FileExplorerMetadataResolution {
    metadataByPath: Map<string, FileBrowserMetadata | null>;
    metadataErrorByPath: Map<string, string>;
    metadataReasonCodeByPath: Map<string, ContentPreviewReasonCode>;
    openFilesFolderSettingsByPath: Set<string>;
}

interface FileExplorerTextPreviewResolution {
    textContentByTarget: Map<string, { content: string } | { errorMessage: string }>;
    textReasonCodeByTarget: Map<string, ContentPreviewReasonCode>;
}

interface FileExplorerFolderPreviewResolution {
    folderPreviewByTarget: Map<string, FileBrowserListPayload | { errorMessage: string }>;
    folderReasonCodeByTarget: Map<string, ContentPreviewReasonCode>;
}

const resolveFileExplorerMetadataForTargets = async (apiClient: JsonApiClient, targets: readonly string[], maxConcurrentFetches: number, signal: AbortSignal): Promise<FileExplorerMetadataResolution> => {
    const metadataByPath = new Map<string, FileBrowserMetadata | null>();
    const metadataErrorByPath = new Map<string, string>();
    const metadataReasonCodeByPath = new Map<string, ContentPreviewReasonCode>();
    const openFilesFolderSettingsByPath = new Set<string>();
    await mapWithConcurrencyLimit(targets, maxConcurrentFetches, async (path) => {
        try {
            const payload = await fetchJson(apiClient, buildFileExplorerMetadataUrl(path), { signal });
            const parsed = parseFileBrowserMetadataPayload(decodeFileExplorerMetadataResponse(payload));
            metadataByPath.set(path, parsed);
            return parsed;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (signal.aborted || isAbortError(runtimeError)) {
                return null;
            }
            errorHandler.warn('InlineMultimediaFileExplorerCardResolver', 'File metadata preview failed', runtimeError);
            const failure = resolveInlinePreviewRequestFailure(runtimeError, { openFilesFolderSettingsOnForbidden: true });
            metadataErrorByPath.set(path, failure.message);
            metadataReasonCodeByPath.set(path, failure.reasonCode);
            if (failure.openFilesFolderSettings) {
                openFilesFolderSettingsByPath.add(path);
            }
            metadataByPath.set(path, null);
            return null;
        }
    });
    return {
        metadataByPath,
        metadataErrorByPath,
        metadataReasonCodeByPath,
        openFilesFolderSettingsByPath
    };
};

const resolveFileExplorerTextPreviewsForTargets = async (apiClient: JsonApiClient, targets: readonly string[], metadataByPath: ReadonlyMap<string, FileBrowserMetadata | null>, maxConcurrentFetches: number, signal: AbortSignal): Promise<FileExplorerTextPreviewResolution> => {
    const textTargets: string[] = [];
    for (const target of targets) {
        const metadata = metadataByPath.get(target) ?? null;
        if (!metadata || metadata.isDirectory) {
            continue;
        }
        if (classifyFileBrowserMimeType(metadata.mimeType) !== 'text') {
            continue;
        }
        textTargets.push(target);
    }
    const textContentByTarget = new Map<string, { content: string } | { errorMessage: string }>();
    const textReasonCodeByTarget = new Map<string, ContentPreviewReasonCode>();
    await mapWithConcurrencyLimit(textTargets, maxConcurrentFetches, async (target) => {
        const metadata = metadataByPath.get(target) ?? null;
        if (!metadata || metadata.isDirectory) {
            return null;
        }
        try {
            const readPayload = await fetchJson(apiClient, buildFileExplorerReadUrl(metadata.path), { signal });
            const readParsed = parseFileBrowserReadPayload(decodeFileExplorerReadResponse(readPayload));
            textContentByTarget.set(target, { content: readParsed.content });
            return readParsed.content;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (signal.aborted || isAbortError(runtimeError)) {
                return null;
            }
            errorHandler.warn('InlineMultimediaFileExplorerCardResolver', 'File text preview read failed', runtimeError);
            const failure = resolveInlinePreviewRequestFailure(runtimeError);
            textContentByTarget.set(target, { errorMessage: failure.message });
            textReasonCodeByTarget.set(target, failure.reasonCode);
            return null;
        }
    });
    return {
        textContentByTarget,
        textReasonCodeByTarget
    };
};

const resolveFileExplorerFolderPreviewsForTargets = async (apiClient: JsonApiClient, targets: readonly string[], maxConcurrentFetches: number, signal: AbortSignal): Promise<FileExplorerFolderPreviewResolution> => {
    const folderPreviewByTarget = new Map<string, FileBrowserListPayload | { errorMessage: string }>();
    const folderReasonCodeByTarget = new Map<string, ContentPreviewReasonCode>();
    await mapWithConcurrencyLimit(targets, maxConcurrentFetches, async (target) => {
        try {
            const payload = await fetchJson(apiClient, buildFileExplorerListUrl(target, FOLDER_PREVIEW_ENTRY_LIMIT), { signal });
            const parsed = parseFileBrowserListPayload(decodeFileExplorerListResponse(payload));
            folderPreviewByTarget.set(target, parsed);
            return parsed;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (signal.aborted || isAbortError(runtimeError)) {
                return null;
            }
            errorHandler.warn('InlineMultimediaFileExplorerCardResolver', 'Folder preview list failed', runtimeError);
            const failure = resolveInlinePreviewRequestFailure(runtimeError);
            folderPreviewByTarget.set(target, { errorMessage: failure.message });
            folderReasonCodeByTarget.set(target, failure.reasonCode);
            return null;
        }
    });
    return {
        folderPreviewByTarget,
        folderReasonCodeByTarget
    };
};

export { FOLDER_PREVIEW_ENTRY_LIMIT, resolveFileExplorerFolderPreviewsForTargets, resolveFileExplorerMetadataForTargets, resolveFileExplorerTextPreviewsForTargets };
export type { FileExplorerFolderPreviewResolution, FileExplorerMetadataResolution, FileExplorerTextPreviewResolution };
