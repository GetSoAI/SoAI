/* SoAI - Chat feature inline multimedia remote link card resolver [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRemoteLinkCardResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { JsonRequestGate, type JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { mapWithConcurrencyLimit } from '@core/concurrency/mapWithConcurrencyLimit.ts';
import { dom } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createPendingCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import { readInlineMediaCardTokenSnapshot, readInlineMediaRemoteUrl, syncInlineMediaRemoteUrlDatasetFromTokenTarget } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { resolvePendingInlineMediaCards, resolvePendingRemoteUrlInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { replaceInlineMediaCardWithIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardReplacement.ts';
import { isHTMLAnchorElementInOwnDocument, resolveEligibleInlineMediaRemoteAnchorHref } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { createInlineMultimediaRemoteLinkReplacementCard } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkCardReplacement.ts';
import { loadRemoteLinkPreviewData } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkPreviewLoader.ts';

class InlineMultimediaRemoteLinkCardResolver {
    readonly #maxConcurrentFetches: number;
    readonly #requestGate: JsonRequestGate;

    constructor(options: { apiClient: JsonApiClient; maxConcurrentFetches: number }) {
        this.#maxConcurrentFetches = clampNumber(options.maxConcurrentFetches, 1, 16);
        this.#requestGate = new JsonRequestGate({ apiClient: options.apiClient });
    }

    replaceEligibleRemoteAnchors(container: HTMLElement, maxAnchors: number): number {
        const doc = container.ownerDocument;
        const anchors = dom.resolveAll('a[href]', container);
        let replacedCount = 0;
        for (const anchor of anchors) {
            if (replacedCount >= maxAnchors) {
                break;
            }
            if (!isHTMLAnchorElementInOwnDocument(anchor)) {
                continue;
            }
            if (anchor.dataset['inlineMediaEnhanced'] === '1') {
                continue;
            }
            const href = resolveEligibleInlineMediaRemoteAnchorHref(anchor);
            if (href === null) {
                continue;
            }
            const pending = createPendingCard(doc, href);
            pending.dataset['inlineMediaStatus'] = 'pending';
            pending.dataset['inlineMediaRemoteUrl'] = href;
            anchor.dataset['inlineMediaEnhanced'] = '1';
            anchor.replaceWith(pending);
            replacedCount += 1;
        }
        return replacedCount;
    }

    async resolvePendingCards(container: HTMLElement, signal: AbortSignal, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder): Promise<void> {
        if (signal.aborted) {
            return;
        }
        const tokenCards = resolvePendingInlineMediaCards(container, 'remote_url');
        for (const card of tokenCards) {
            syncInlineMediaRemoteUrlDatasetFromTokenTarget(card);
        }
        const pendingCards = resolvePendingRemoteUrlInlineMediaCards(container);
        if (pendingCards.length <= 0) {
            return;
        }

        const uniqueUrls = [...new Set(pendingCards.map((card) => readInlineMediaRemoteUrl(card)).filter(Boolean))];
        const { previewByUrl, failureByUrl, excerptByTextPreviewUrl } = await loadRemoteLinkPreviewData({
            urls: uniqueUrls,
            maxConcurrentFetches: this.#maxConcurrentFetches,
            requestGate: this.#requestGate,
            signal
        });
        if (signal.aborted) {
            return;
        }

        const doc = container.ownerDocument;
        await mapWithConcurrencyLimit(pendingCards, this.#maxConcurrentFetches, async (card) => {
            if (signal.aborted) {
                return;
            }
            if (!card.isConnected) {
                return;
            }
            const token = readInlineMediaCardTokenSnapshot(card);
            const url = readInlineMediaRemoteUrl(card);
            if (!url) {
                return;
            }
            const preview = previewByUrl.get(url) ?? null;
            const replacementCard = createInlineMultimediaRemoteLinkReplacementCard({
                doc,
                excerptByTextPreviewUrl,
                failureReason: failureByUrl.get(url) ?? null,
                feedbackRecorder,
                preview,
                referenceUrl: url,
                tokenLabel: token.tokenLabel ? token.tokenLabel : '',
                tokenRaw: token.tokenRaw ? token.tokenRaw : url
            });
            replaceInlineMediaCardWithIdentity(card, replacementCard, {
                tokenType: token.tokenType,
                tokenTarget: token.tokenTarget,
                tokenLabel: token.tokenLabel,
                tokenRaw: token.tokenRaw,
                remoteUrl: url
            });
        });
    }
}

export { InlineMultimediaRemoteLinkCardResolver };
