/* SoAI - Chat feature inline multimedia local text preview reader [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaLocalTextPreviewReader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeFileExplorerReadResponse } from '@core/api/contracts/fileExplorerContracts.ts';
import { fetchJson, type JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { mapWithConcurrencyLimit } from '@core/concurrency/mapWithConcurrencyLimit.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseFileBrowserReadPayload } from '@core/fileexplorerbrowser/payloads.ts';
import type { ContentPreviewReasonCode } from '@features/chat/contentPreviewContracts.ts';
import { resolveInlinePreviewRequestFailure } from '@features/chat/message/enhancers/inlineMultimediaRequestFailure.ts';

const MAX_CONCURRENT_TEXT_READS = 4;

type LocalTextPreviewReadResult = { content: string } | { errorMessage: string; reasonCode: ContentPreviewReasonCode };

const readLocalTextPreview = async (apiClient: JsonApiClient, previewUrl: string, signal: AbortSignal): Promise<LocalTextPreviewReadResult | null> => {
    try {
        const readPayload = await fetchJson(apiClient, previewUrl, { signal });
        const parsed = parseFileBrowserReadPayload(decodeFileExplorerReadResponse(readPayload));
        return { content: parsed.content };
    } catch (error) {
        const runtimeError = ensureError(error);
        if (signal.aborted || isAbortError(runtimeError)) {
            return null;
        }
        errorHandler.warn('InlineMultimediaLocalTextPreviewReader', 'Local text preview read failed', runtimeError);
        const failure = resolveInlinePreviewRequestFailure(runtimeError);
        return { errorMessage: failure.message, reasonCode: failure.reasonCode };
    }
};

const readLocalTextPreviews = async (
    targets: string[],
    options: {
        apiClient: JsonApiClient;
        resolvePreviewUrl: (target: string) => string | null;
        signal: AbortSignal;
    }
): Promise<Map<string, LocalTextPreviewReadResult>> => {
    const textContentByTarget = new Map<string, LocalTextPreviewReadResult>();
    await mapWithConcurrencyLimit(targets, MAX_CONCURRENT_TEXT_READS, async (target) => {
        const previewUrl = options.resolvePreviewUrl(target);
        if (!previewUrl) {
            return null;
        }
        const result = await readLocalTextPreview(options.apiClient, previewUrl, options.signal);
        if (!result || options.signal.aborted) {
            return null;
        }
        textContentByTarget.set(target, result);
        return null;
    });
    return textContentByTarget;
};

export { readLocalTextPreviews };
