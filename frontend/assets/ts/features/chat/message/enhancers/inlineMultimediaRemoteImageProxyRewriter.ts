/* SoAI - Chat feature inline multimedia remote image proxy rewriter [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteImageProxyRewriter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PROXY_PREFIX, buildMediaProxyUrl, isMediaProxyUrl } from '@core/api/endpoints/webuiPreviewPaths.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import { createErrorCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import { isHTMLElementInOwnDocument, isHTMLImageElementInOwnDocument, shouldSkipInlineMediaImage } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';

const isAlreadyProxyUrl = (url: string): boolean => {
    if (url.startsWith(PROXY_PREFIX)) {
        return true;
    }
    if (!isAbsoluteHttpUrl(url)) {
        return false;
    }
    try {
        const parsed = new URL(url);
        return isMediaProxyUrl(parsed);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('InlineMultimediaRemoteImageProxyRewriter', 'Remote image proxy URL parse failed', runtimeError);
        return false;
    }
};

const bindProxyFailureHandler = (img: HTMLImageElement, originalUrl: string, downloadUrl: string, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder): void => {
    if (img.dataset['inlineMediaProxyFailureBound'] === '1') {
        return;
    }
    img.dataset['inlineMediaProxyFailureBound'] = '1';
    img.addEventListener(
        'error',
        () => {
            const closestFigure = img.closest('figure');
            const replacementTarget = closestFigure !== null && isHTMLElementInOwnDocument(closestFigure) ? closestFigure : img;
            if (!replacementTarget.isConnected) {
                return;
            }
            feedbackRecorder.recordFailure({ referenceType: 'remote_url', target: originalUrl, reasonCode: 'request_failed' });
            const doc = img.ownerDocument;
            const title = (img.getAttribute('alt') ?? '').trim() || originalUrl;
            replacementTarget.replaceWith(
                createErrorCard(doc, title, i18n.t('chat.inlinePreviews.requestFailedMessage'), {
                    openFileExplorerHref: null,
                    searchHref: null,
                    copyValue: originalUrl,
                    openSourceHref: originalUrl,
                    downloadHref: downloadUrl
                })
            );
        },
        { once: true }
    );
};

const rewriteRemoteImagesToProxy = (container: HTMLElement, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder): void => {
    const images = dom.resolveAll('img', container);
    for (const img of images) {
        if (!isHTMLImageElementInOwnDocument(img)) {
            continue;
        }
        if (shouldSkipInlineMediaImage(img)) {
            continue;
        }
        const src = img.getAttribute('src') ?? '';
        if (!isAbsoluteHttpUrl(src)) {
            continue;
        }
        if (isAlreadyProxyUrl(src)) {
            continue;
        }
        bindProxyFailureHandler(img, src, buildMediaProxyUrl(src, true), feedbackRecorder);
        const proxyUrl = buildMediaProxyUrl(src, false);
        const downloadUrl = buildMediaProxyUrl(src, true);
        img.src = proxyUrl;
        if (img.dataset['mediaPreviewUrl']) {
            img.dataset['mediaPreviewUrl'] = proxyUrl;
        }
        if (!img.dataset['mediaOpenSourceUrl']) {
            img.dataset['mediaOpenSourceUrl'] = src;
        }
        if (!img.dataset['mediaSourceType']) {
            img.dataset['mediaSourceType'] = 'url';
            img.dataset['mediaSourceValue'] = src;
        }
        img.dataset['mediaDownloadUrl'] = downloadUrl;
    }
};

export { rewriteRemoteImagesToProxy };
