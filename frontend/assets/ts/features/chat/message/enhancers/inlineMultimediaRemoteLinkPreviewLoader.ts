/* SoAI - Chat feature inline multimedia remote link preview loader [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkPreviewLoader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildLinkPreviewUrl } from '@core/api/endpoints/webuiPreviewPaths.ts';
import { JsonRequestGate } from '@core/api/jsonRequestGate.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import { mapWithConcurrencyLimit } from '@core/concurrency/mapWithConcurrencyLimit.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { parseRemoteLinkPreview, parseRemoteTextPreviewPayload, type RemoteLinkPreview } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPayloads.ts';
import { resolveRemoteLinkPreviewFailureReason, type RemoteLinkPreviewFailureReason } from '@features/chat/message/enhancers/inlineMultimediaRequestFailure.ts';

type RemoteTextExcerptLookupResult = { excerpt: string } | { errorMessage: string };

interface LoadRemoteLinkPreviewDataOptions {
    maxConcurrentFetches: number;
    requestGate: JsonRequestGate;
    signal: AbortSignal;
    urls: readonly string[];
}

interface LoadRemoteLinkPreviewDataResult {
    excerptByTextPreviewUrl: Map<string, RemoteTextExcerptLookupResult>;
    failureByUrl: Map<string, RemoteLinkPreviewFailureReason>;
    previewByUrl: Map<string, RemoteLinkPreview>;
}

const loadRemoteLinkPreviewData = async (options: LoadRemoteLinkPreviewDataOptions): Promise<LoadRemoteLinkPreviewDataResult> => {
    const uniqueUrls = [...new Set(options.urls)];
    const previewByUrl = new Map<string, RemoteLinkPreview>();
    const failureByUrl = new Map<string, RemoteLinkPreviewFailureReason>();
    await mapWithConcurrencyLimit(uniqueUrls, options.maxConcurrentFetches, async (url) => {
        try {
            const payload = requireJsonResponsePayload(await options.requestGate.requestJson(buildLinkPreviewUrl(url), { signal: options.signal }), 'Inline multimedia preview');
            const parsed = parseRemoteLinkPreview(payload);
            previewByUrl.set(url, parsed);
            return parsed;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (options.signal.aborted || isAbortError(runtimeError)) {
                return null;
            }
            errorHandler.warn('InlineMultimediaRemoteLinkCardResolver', 'Remote link preview fetch failed', runtimeError);
            failureByUrl.set(url, resolveRemoteLinkPreviewFailureReason(runtimeError));
            return null;
        }
    });
    if (options.signal.aborted) {
        return {
            previewByUrl,
            failureByUrl,
            excerptByTextPreviewUrl: new Map<string, RemoteTextExcerptLookupResult>()
        };
    }

    const textPreviewUrls: string[] = [];
    for (const preview of previewByUrl.values()) {
        if (!preview.excerptAvailable) {
            continue;
        }
        if (preview.type !== 'text' && preview.type !== 'link') {
            continue;
        }
        textPreviewUrls.push(preview.previewUrl);
    }
    const uniqueTextPreviewUrls = [...new Set(textPreviewUrls)];
    const excerptByTextPreviewUrl = new Map<string, RemoteTextExcerptLookupResult>();
    await mapWithConcurrencyLimit(uniqueTextPreviewUrls, options.maxConcurrentFetches, async (textUrl) => {
        try {
            const textPayload = requireJsonResponsePayload(await options.requestGate.requestJson(textUrl, { signal: options.signal }), 'Inline multimedia text preview');
            const parsed = parseRemoteTextPreviewPayload(textPayload);
            excerptByTextPreviewUrl.set(textUrl, { excerpt: parsed.excerpt });
            return parsed.excerpt;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (options.signal.aborted || isAbortError(runtimeError)) {
                return null;
            }
            errorHandler.warn('InlineMultimediaRemoteLinkCardResolver', 'Remote text preview fetch failed', runtimeError);
            excerptByTextPreviewUrl.set(textUrl, { errorMessage: i18n.t('chat.inlinePreviews.requestFailedMessage') });
            return null;
        }
    });

    return { previewByUrl, failureByUrl, excerptByTextPreviewUrl };
};

export { loadRemoteLinkPreviewData };
export type { LoadRemoteLinkPreviewDataResult, RemoteTextExcerptLookupResult };
