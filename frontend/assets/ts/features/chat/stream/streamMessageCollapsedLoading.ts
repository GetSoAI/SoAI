/* SoAI - Chat feature stream message collapsed loading [frontend/assets/ts/features/chat/stream/streamMessageCollapsedLoading.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { resolveHTMLElement, syncAttributes, syncClass } from '@core/dom/patching.ts';
import { applyAssistantMessageTextMarkup } from '@features/chat/message/assistantMessageTextDomApply.ts';
import { captureAssistantViewportStability, restoreAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { patchInlineActivityHeaderChildrenInPlace } from '@features/chat/message/messageview/inlineActivityHeaderChildrenPatching.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_SUMMARY_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { resolveCollapsedLoadingContentSegments } from '@features/chat/message/messageview/collapsedLoadingSummaryRendering.ts';
import { collectMermaidContainersByKey, resetStreamingActivityCacheState, restoreMermaidContainersByKey } from '@features/chat/stream/streamDomCache.ts';
import { syncActiveStreamingTextRun } from '@features/chat/stream/streamMessageActiveTextSync.ts';
import { patchTimelineChildren } from '@features/chat/stream/streamMessageTimelineChildren.ts';
import { isPassiveStreamRenderPatchType } from '@features/chat/stream/streamMessageRenderMode.ts';
import { syncStreamingMessagePassiveState } from '@features/chat/stream/streamMessageRenderState.ts';
import { ensureStreamingSegmentsContainer } from '@features/chat/stream/streamMessageStreamingStructure.ts';
import { applyKeyedScrollableState, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';
import type { RenderStreamingMessageContentArguments, RenderStreamingMessageContentResult } from '@features/chat/stream/streamMessageRenderingContracts.ts';

const patchCollapsedLoadingSummary = (currentSummary: HTMLElement, nextSummary: HTMLElement): boolean => {
    const currentHeader = resolveHTMLElement(':scope > .inline-activity-header', currentSummary);
    const nextHeader = resolveHTMLElement(':scope > .inline-activity-header', nextSummary);
    if (!(currentHeader instanceof HTMLElement) || !(nextHeader instanceof HTMLElement)) {
        return false;
    }
    let changed = false;
    if (syncClass(currentSummary, nextSummary)) {
        changed = true;
    }
    if (syncAttributes({ target: currentSummary, source: nextSummary })) {
        changed = true;
    }
    if (patchInlineActivityHeaderChildrenInPlace(currentHeader, nextHeader)) {
        changed = true;
    }
    return changed;
};

const patchCollapsedLoadingChrome = (target: HTMLElement, contentHtml: TrustedHtml): { patched: boolean; changed: boolean } => {
    const currentSummary = dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, target);
    const currentContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, target);
    if (!(currentSummary instanceof HTMLElement) || !(currentContent instanceof HTMLElement)) {
        return { patched: false, changed: false };
    }
    const scratch = target.ownerDocument.createElement('div');
    replaceChildrenFromTrustedHtml({ element: scratch, html: contentHtml, context: scratch });
    const nextSummary = dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, scratch);
    const nextContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, scratch);
    if (!(nextSummary instanceof HTMLElement) || !(nextContent instanceof HTMLElement)) {
        return { patched: false, changed: false };
    }
    let changed = patchCollapsedLoadingSummary(currentSummary, nextSummary);
    if (syncAttributes({ target: currentContent, source: nextContent })) {
        changed = true;
    }
    return { patched: true, changed };
};

const patchCollapsedLoadingStreamingContent = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement, resolvedSegments: ReturnType<RenderStreamingMessageContentArguments['messageManager']['resolveMessageContentSegments']> | null): { supported: boolean; changed: boolean } => {
    const currentContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, target);
    if (!(currentContent instanceof HTMLElement)) {
        return { supported: true, changed: false };
    }
    const segments = resolveCollapsedLoadingContentSegments(resolvedSegments ?? inputArguments.messageManager.resolveMessageContentSegments(inputArguments.message));
    const { streamSegments, streamText } = ensureStreamingSegmentsContainer(currentContent, inputArguments.cached);
    const timelineResult = patchTimelineChildren(inputArguments.message, inputArguments.cached, inputArguments.messageManager, streamSegments, segments);
    if (!timelineResult.supported) {
        return { supported: false, changed: false };
    }
    let changed = timelineResult.updated;
    const activeTextSync = syncActiveStreamingTextRun({
        activeTextRun: timelineResult.activeTextRun,
        messageArguments: inputArguments,
        streamText
    });
    if (activeTextSync.updated) {
        changed = true;
    }
    if (activeTextSync.needsPostRender) {
        for (const target of activeTextSync.postRenderTargets) {
            inputArguments.messageManager.postRenderRequest(target, 'streamingText');
        }
    }
    if (timelineResult.updated) {
        inputArguments.messageManager.postRender(streamSegments);
    }
    return { supported: true, changed };
};

const renderCollapsedLoadingMessageContent = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): RenderStreamingMessageContentResult => {
    const renderedContent = inputArguments.messageManager.renderActiveStreamMessageTextContent(inputArguments.message);
    const contentHtml = renderedContent.html;
    if (inputArguments.cached.lastCollapsedLoadingHtml === contentHtml && inputArguments.cached.renderMode === 'collapsedLoading') {
        const passiveStateUpdated = syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached });
        return {
            handled: true,
            invalidatedCache: false,
            updatedMarkup: passiveStateUpdated,
            target
        };
    }

    const preservedScroll = readKeyedScrollableState(target);
    const preservedMermaidContainers = collectMermaidContainersByKey(target);
    const viewportStability = captureAssistantViewportStability(target);
    const collapsedMarkup = toTrustedUiHtml(contentHtml);
    const includeContent = isPassiveStreamRenderPatchType(inputArguments.patchType) === false;
    const renderModeChanged = inputArguments.cached.renderMode !== 'collapsedLoading';
    const patchResult = patchCollapsedLoadingChrome(target, collapsedMarkup);
    let rebuiltChrome = false;
    if (!patchResult.patched) {
        applyAssistantMessageTextMarkup(target, contentHtml);
        rebuiltChrome = true;
    }
    const streamingContentPatch = includeContent ? patchCollapsedLoadingStreamingContent(inputArguments, target, renderedContent.resolvedSegments) : { supported: true, changed: false };
    if (!streamingContentPatch.supported) {
        return {
            handled: false,
            invalidatedCache: true,
            updatedMarkup: false,
            target
        };
    }
    if (rebuiltChrome) {
        restoreMermaidContainersByKey(target, preservedMermaidContainers);
        if (preservedScroll) {
            applyKeyedScrollableState(target, preservedScroll);
        }
        restoreAssistantViewportStability(viewportStability);
    }
    inputArguments.cached.lastCollapsedLoadingHtml = contentHtml;
    resetStreamingActivityCacheState(inputArguments.cached);
    inputArguments.cached.renderMode = 'collapsedLoading';
    if (rebuiltChrome || streamingContentPatch.changed) {
        inputArguments.messageManager.postRender(target);
    }
    const passiveStateUpdated = syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached });
    return {
        handled: true,
        invalidatedCache: false,
        updatedMarkup: renderModeChanged || rebuiltChrome || patchResult.changed || streamingContentPatch.changed || passiveStateUpdated,
        target
    };
};

export { renderCollapsedLoadingMessageContent };
