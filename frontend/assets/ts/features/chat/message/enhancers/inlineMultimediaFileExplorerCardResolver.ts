/* SoAI - Chat feature inline multimedia file explorer card resolver [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaFileExplorerCardResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildFileExplorerPreviewUrl } from '@core/api/endpoints/fileExplorerPaths.ts';
import type { JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { mapWithConcurrencyLimit } from '@core/concurrency/mapWithConcurrencyLimit.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { parentVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { readInlineMediaCardTokenSnapshot } from '@features/chat/message/enhancers/inlineMultimediaCardDataset.ts';
import { resolveInlineMediaCardReferenceFromSnapshot } from '@features/chat/message/enhancers/inlineMultimediaCardReference.ts';
import { replaceInlineMediaCardWithIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardReplacement.ts';
import { createErrorCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { resolveFileExplorerFolderPreviewsForTargets, resolveFileExplorerMetadataForTargets, resolveFileExplorerTextPreviewsForTargets } from '@features/chat/message/enhancers/inlineMultimediaFileExplorerResolution.ts';
import { mapFileExplorerListToFolderPreview } from '@features/chat/message/enhancers/inlineMultimediaFolderPreviewMapping.ts';
import { buildFileExplorerDeepLink, buildFileExplorerSearchLink } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';
import { resolvePendingInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { createResolvedInlineMediaReplacementCard, type ResolvedInlineMediaPreviewDescriptor } from '@features/chat/message/enhancers/inlineMultimediaResolvedCardFactory.ts';
import { resolveInlineMediaPathLeaf } from '@features/chat/message/enhancers/inlineMultimediaTargetPaths.ts';

class InlineMultimediaFileExplorerCardResolver {
    readonly #apiClient: JsonApiClient;
    readonly #maxConcurrentFetches: number;

    constructor(options: { apiClient: JsonApiClient; maxConcurrentFetches: number }) {
        this.#apiClient = options.apiClient;
        this.#maxConcurrentFetches = clampNumber(options.maxConcurrentFetches, 1, 16);
    }

    async resolvePendingCards(container: HTMLElement, signal: AbortSignal, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder): Promise<void> {
        if (signal.aborted) {
            return;
        }
        const pendingCards = resolvePendingInlineMediaCards(container, 'virtual_path');
        if (pendingCards.length <= 0) {
            return;
        }

        const targets = [...new Set(pendingCards.map((card) => readInlineMediaCardTokenSnapshot(card).tokenTarget).filter(Boolean))];
        if (targets.length <= 0) {
            return;
        }

        const metadataResolution = await resolveFileExplorerMetadataForTargets(this.#apiClient, targets, this.#maxConcurrentFetches, signal);
        if (signal.aborted) {
            return;
        }

        const folderTargets = targets.filter((target) => {
            const metadata = metadataResolution.metadataByPath.get(target) ?? null;
            return Boolean(metadata && metadata.isDirectory);
        });
        const [textResolution, folderResolution] = await Promise.all([resolveFileExplorerTextPreviewsForTargets(this.#apiClient, targets, metadataResolution.metadataByPath, this.#maxConcurrentFetches, signal), resolveFileExplorerFolderPreviewsForTargets(this.#apiClient, folderTargets, this.#maxConcurrentFetches, signal)]);
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
            const target = token.tokenTarget;
            if (!target) {
                return;
            }
            const reference = resolveInlineMediaCardReferenceFromSnapshot(token, target, i18n.t('chat.inlinePreviews.virtualPathTitle'));
            const label = reference.label;
            const rawToken = reference.rawToken;
            const cardIdentity = reference.identity;
            const metadata = metadataResolution.metadataByPath.get(target) ?? null;
            if (!metadata) {
                const filename = resolveInlineMediaPathLeaf(target) || target;
                const reason = metadataResolution.metadataErrorByPath.get(target) ?? i18n.t('chat.inlinePreviews.unavailableMessage');
                const reasonCode = metadataResolution.metadataReasonCodeByPath.get(target) ?? 'request_failed';
                feedbackRecorder.recordFailure({ referenceType: 'virtual_path', target, reasonCode });
                const replacement = createErrorCard(doc, label, reason, {
                    openFileExplorerHref: null,
                    searchHref: buildFileExplorerSearchLink(filename),
                    copyValue: rawToken,
                    openFilesFolderSettings: metadataResolution.openFilesFolderSettingsByPath.has(target)
                });
                replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                return;
            }

            const directory = parentVirtualPath(metadata.path);
            const openExplorerHref = metadata.isDirectory ? buildFileExplorerDeepLink({ directoryPath: metadata.path, highlightPath: null, search: null }) : buildFileExplorerDeepLink({ directoryPath: directory, highlightPath: metadata.path, search: metadata.name });
            if (metadata.isDirectory) {
                const folderResult = folderResolution.folderPreviewByTarget.get(target) ?? null;
                if (!folderResult || 'errorMessage' in folderResult) {
                    const reasonCode = folderResolution.folderReasonCodeByTarget.get(target) ?? 'request_failed';
                    const message = folderResult && 'errorMessage' in folderResult ? folderResult.errorMessage : i18n.t('chat.inlinePreviews.requestFailedMessage');
                    feedbackRecorder.recordFailure({ referenceType: 'virtual_path', target, reasonCode });
                    const replacement = createErrorCard(doc, label, message, {
                        openFileExplorerHref: openExplorerHref,
                        searchHref: null,
                        copyValue: rawToken
                    });
                    replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                    return;
                }
                const descriptor: ResolvedInlineMediaPreviewDescriptor = {
                    type: 'folder',
                    title: label,
                    target,
                    sourcePath: target,
                    rawToken,
                    openFileExplorerHref: openExplorerHref,
                    downloadHref: null,
                    downloadName: null,
                    previewUrl: null,
                    mimeType: metadata.mimeType,
                    size: metadata.size,
                    textPreviewContent: null,
                    folderPreview: mapFileExplorerListToFolderPreview(folderResult)
                };
                const replacement = createResolvedInlineMediaReplacementCard({ doc, ...descriptor });
                replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                return;
            }

            const type = classifyFileBrowserMimeType(metadata.mimeType);
            if (type === 'text') {
                const textResult = textResolution.textContentByTarget.get(target) ?? null;
                if (!textResult) {
                    feedbackRecorder.recordFailure({ referenceType: 'virtual_path', target, reasonCode: 'request_failed' });
                    const replacement = createErrorCard(doc, label, i18n.t('chat.inlinePreviews.unavailableMessage'), { openFileExplorerHref: openExplorerHref, searchHref: null, copyValue: rawToken });
                    replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                    return;
                }
                if ('errorMessage' in textResult) {
                    const reasonCode = textResolution.textReasonCodeByTarget.get(target) ?? 'request_failed';
                    feedbackRecorder.recordFailure({ referenceType: 'virtual_path', target, reasonCode });
                    const replacement = createErrorCard(doc, label, textResult.errorMessage, { openFileExplorerHref: openExplorerHref, searchHref: null, copyValue: rawToken });
                    replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                    return;
                }
                const descriptor: ResolvedInlineMediaPreviewDescriptor = {
                    type: 'text',
                    title: label,
                    target,
                    sourcePath: target,
                    rawToken,
                    openFileExplorerHref: openExplorerHref,
                    downloadHref: buildFileExplorerPreviewUrl(metadata.path, true),
                    downloadName: metadata.name,
                    previewUrl: null,
                    mimeType: metadata.mimeType,
                    size: metadata.size,
                    textPreviewContent: textResult.content,
                    folderPreview: null
                };
                const replacement = createResolvedInlineMediaReplacementCard({ doc, ...descriptor });
                replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
                return;
            }

            const downloadUrl = buildFileExplorerPreviewUrl(metadata.path, true);
            const descriptor: ResolvedInlineMediaPreviewDescriptor = {
                type,
                title: label,
                target,
                sourcePath: target,
                rawToken,
                openFileExplorerHref: openExplorerHref,
                downloadHref: downloadUrl,
                downloadName: metadata.name,
                previewUrl: type === 'image' || type === 'audio' || type === 'video' ? buildFileExplorerPreviewUrl(metadata.path, false) : null,
                mimeType: metadata.mimeType,
                size: metadata.size,
                textPreviewContent: null,
                folderPreview: null
            };
            const replacement = createResolvedInlineMediaReplacementCard({ doc, ...descriptor });
            replaceInlineMediaCardWithIdentity(card, replacement, cardIdentity);
        });
    }
}

export { InlineMultimediaFileExplorerCardResolver };
