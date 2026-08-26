/* SoAI - Chat feature inline multimedia absolute path card resolver [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaAbsolutePathCardResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildWebuiConversationAbsolutePathsResolvePath } from '@core/api/endpoints/webuiConversationPaths.ts';
import { fetchJson, type JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveInlineMediaCardReference } from '@features/chat/message/enhancers/inlineMultimediaCardReference.ts';
import { replaceInlineMediaCardWithIdentity } from '@features/chat/message/enhancers/inlineMultimediaCardReplacement.ts';
import { createErrorCard } from '@features/chat/message/enhancers/inlineMultimediaCardsStatus.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { buildFileExplorerSearchLink } from '@features/chat/message/enhancers/inlineMultimediaUrls.ts';
import { readLocalTextPreviews } from '@features/chat/message/enhancers/inlineMultimediaLocalTextPreviewReader.ts';
import { parseAbsolutePathsResolveResult, resolveAbsolutePathsResultPreviewFailure, type AbsolutePathsResolveResult } from '@features/chat/message/enhancers/inlineMultimediaAbsolutePathResolvePayload.ts';
import { resolveFileExplorerFolderPreviewsForTargets } from '@features/chat/message/enhancers/inlineMultimediaFileExplorerResolution.ts';
import { mapFileExplorerListToFolderPreview } from '@features/chat/message/enhancers/inlineMultimediaFolderPreviewMapping.ts';
import { groupPendingInlineMediaCardsByTarget, resolvePendingInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { createResolvedInlineMediaReplacementCard } from '@features/chat/message/enhancers/inlineMultimediaResolvedCardFactory.ts';
import { resolveInlineMediaPathLeaf } from '@features/chat/message/enhancers/inlineMultimediaTargetPaths.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const MAX_FOLDER_PREVIEW_FETCHES = 4;

class InlineMultimediaAbsolutePathCardResolver {
    readonly #apiClient: JsonApiClient;

    constructor(apiClient: JsonApiClient) {
        this.#apiClient = apiClient;
    }

    async resolvePendingCards(container: HTMLElement, conversationId: string, signal: AbortSignal, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder): Promise<void> {
        if (signal.aborted) {
            return;
        }
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const pendingCards = resolvePendingInlineMediaCards(container, 'absolute_path');
        if (pendingCards.length <= 0) {
            return;
        }

        const grouping = groupPendingInlineMediaCardsByTarget(pendingCards);
        const targets = grouping.targets;
        const cardsByTarget = grouping.cardsByTarget;
        if (targets.length <= 0) {
            return;
        }

        const doc = container.ownerDocument;
        let results: AbsolutePathsResolveResult[] = [];
        try {
            const payload = await fetchJson(this.#apiClient, buildWebuiConversationAbsolutePathsResolvePath(normalizedConversationId), {
                method: 'POST',
                body: { paths: targets },
                signal
            });
            results = parseAbsolutePathsResolveResult(requireJsonResponsePayload(payload, 'Inline multimedia absolute path resolve'));
        } catch (error) {
            const runtimeError = ensureError(error);
            if (signal.aborted || isAbortError(runtimeError)) {
                return;
            }
            errorHandler.warn('InlineMultimediaAbsolutePathCardResolver', 'Absolute paths resolve request failed', runtimeError);
            const reason = i18n.t('chat.inlinePreviews.requestFailedMessage');
            for (const card of pendingCards) {
                const reference = resolveInlineMediaCardReference(card, '', i18n.t('chat.inlinePreviews.absolutePathTitle'));
                feedbackRecorder.recordFailure({ referenceType: 'absolute_path', target: reference.failureTarget, reasonCode: 'request_failed' });
                const replacement = createErrorCard(doc, reference.label, reason, {
                    openFileExplorerHref: null,
                    searchHref: null,
                    copyValue: reference.rawToken
                });
                replaceInlineMediaCardWithIdentity(card, replacement, reference.identity);
            }
            return;
        }

        const resultByPath = new Map<string, AbsolutePathsResolveResult>();
        for (const result of results) {
            resultByPath.set(result.path, result);
        }

        const textReadTargets: string[] = [];
        const folderPreviewTargets: string[] = [];
        for (const target of targets) {
            const result = resultByPath.get(target) ?? null;
            if (result && result.status === 'ok' && result.type === 'text' && result.previewUrl) {
                textReadTargets.push(target);
            }
            if (result && result.status === 'ok' && result.type === 'folder') {
                folderPreviewTargets.push(result.virtualPath);
            }
        }
        const [textContentByTarget, folderResolution] = await Promise.all([
            readLocalTextPreviews(textReadTargets, {
                apiClient: this.#apiClient,
                resolvePreviewUrl: (target: string): string | null => {
                    const result = resultByPath.get(target) ?? null;
                    if (!result || result.status !== 'ok' || result.type !== 'text' || !result.previewUrl) {
                        return null;
                    }
                    return result.previewUrl;
                },
                signal
            }),
            resolveFileExplorerFolderPreviewsForTargets(this.#apiClient, [...new Set(folderPreviewTargets)], MAX_FOLDER_PREVIEW_FETCHES, signal)
        ]);
        if (signal.aborted) {
            return;
        }

        for (const target of targets) {
            if (signal.aborted) {
                return;
            }
            const result = resultByPath.get(target) ?? null;
            const cardList = cardsByTarget.get(target) ?? [];
            for (const existingCard of cardList) {
                if (signal.aborted) {
                    return;
                }
                if (!existingCard.isConnected) {
                    continue;
                }
                const reference = resolveInlineMediaCardReference(existingCard, target, i18n.t('chat.inlinePreviews.absolutePathTitle'));
                const label = reference.label;
                const rawToken = reference.rawToken;
                const cardIdentity = reference.identity;
                if (!result || result.status === 'error') {
                    const openHref = result && result.status === 'error' ? result.openFileExplorerUrl : null;
                    const failure = resolveAbsolutePathsResultPreviewFailure(result);
                    const filename = resolveInlineMediaPathLeaf(target) || target;
                    feedbackRecorder.recordFailure({ referenceType: 'absolute_path', target, reasonCode: failure.reasonCode });
                    const replacement = createErrorCard(doc, label, failure.message, {
                        openFileExplorerHref: openHref,
                        searchHref: buildFileExplorerSearchLink(filename),
                        copyValue: rawToken,
                        openFilesFolderSettings: failure.openFilesFolderSettings
                    });
                    replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
                    continue;
                }

                const title = label;
                const downloadHref = result.downloadUrl;
                const openExplorerHref = result.openFileExplorerUrl;
                const effectiveType = (result.type === 'image' || result.type === 'audio' || result.type === 'video' || result.type === 'text') && result.previewUrl === null ? 'file' : result.type;
                if (effectiveType === 'folder') {
                    const folderResult = folderResolution.folderPreviewByTarget.get(result.virtualPath) ?? null;
                    if (!folderResult || 'errorMessage' in folderResult) {
                        const reasonCode = folderResolution.folderReasonCodeByTarget.get(result.virtualPath) ?? 'request_failed';
                        const message = folderResult && 'errorMessage' in folderResult ? folderResult.errorMessage : i18n.t('chat.inlinePreviews.requestFailedMessage');
                        feedbackRecorder.recordFailure({ referenceType: 'absolute_path', target, reasonCode });
                        const replacement = createErrorCard(doc, title, message, { openFileExplorerHref: openExplorerHref, searchHref: null, copyValue: rawToken });
                        replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
                        continue;
                    }
                    const replacement = createResolvedInlineMediaReplacementCard({
                        doc,
                        type: 'folder',
                        title,
                        target,
                        sourcePath: result.virtualPath,
                        rawToken,
                        openFileExplorerHref: openExplorerHref,
                        downloadHref: null,
                        downloadName: null,
                        previewUrl: null,
                        mimeType: result.mimeType,
                        size: result.size,
                        textPreviewContent: null,
                        folderPreview: mapFileExplorerListToFolderPreview(folderResult)
                    });
                    replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
                    continue;
                }
                let textPreviewContent: string | null = null;
                if (effectiveType === 'text') {
                    const textResult = textContentByTarget.get(target) ?? null;
                    if (!textResult) {
                        feedbackRecorder.recordFailure({ referenceType: 'absolute_path', target, reasonCode: 'request_failed' });
                        const replacement = createErrorCard(doc, title, i18n.t('chat.inlinePreviews.unavailableMessage'), { openFileExplorerHref: openExplorerHref, searchHref: null, copyValue: rawToken });
                        replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
                        continue;
                    }
                    if ('errorMessage' in textResult) {
                        feedbackRecorder.recordFailure({ referenceType: 'absolute_path', target, reasonCode: textResult.reasonCode });
                        const replacement = createErrorCard(doc, title, textResult.errorMessage, { openFileExplorerHref: openExplorerHref, searchHref: null, copyValue: rawToken });
                        replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
                        continue;
                    }
                    textPreviewContent = textResult.content;
                }
                const replacement = createResolvedInlineMediaReplacementCard({
                    doc,
                    type: effectiveType,
                    title,
                    target,
                    sourcePath: result.virtualPath,
                    rawToken,
                    openFileExplorerHref: openExplorerHref,
                    downloadHref,
                    downloadName: null,
                    previewUrl: result.previewUrl,
                    mimeType: result.mimeType,
                    size: result.size,
                    textPreviewContent,
                    folderPreview: null
                });
                replaceInlineMediaCardWithIdentity(existingCard, replacement, cardIdentity);
            }
        }
    }
}

export { InlineMultimediaAbsolutePathCardResolver };
