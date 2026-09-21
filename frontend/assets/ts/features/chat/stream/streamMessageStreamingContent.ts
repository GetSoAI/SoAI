/* SoAI - Chat feature stream message streaming content [frontend/assets/ts/features/chat/stream/streamMessageStreamingContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { appendedTextIntroducesSoaiPathToken } from '@core/soailinks/codec.ts';
import { syncActiveStreamingTextRun, syncVerifiedStreamingTextAppend } from '@features/chat/stream/streamMessageActiveTextSync.ts';
import { resolveStreamActivityVisibleState, resolveStreamTimelineLength } from '@features/chat/stream/streamActivityVisibleState.ts';
import { ensureStreamingStructure } from '@features/chat/stream/streamMessageStreamingStructure.ts';
import { patchTimelineChildren, type ActiveStreamingTextRun } from '@features/chat/stream/streamMessageTimelineChildren.ts';
import { isPassiveStreamRenderPatchType, messageHasStreamText } from '@features/chat/stream/streamMessageRenderMode.ts';
import { syncStreamingMessagePassiveState } from '@features/chat/stream/streamMessageRenderState.ts';
import type { RenderStreamingMessageContentArguments, RenderStreamingMessageContentResult } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { syncStreamingSpinnerActivityFlags } from '@features/chat/stream/streamMessageSpinnerStatusActivityFlags.ts';
import { reconcileStreamingSpinnerStatusSubtree } from '@features/chat/stream/streamMessageSpinnerStatusRuntime.ts';

const isConnectedStreamingNode = (target: HTMLElement, node: HTMLElement | null): node is HTMLElement => node instanceof HTMLElement && node.isConnected && target.contains(node);

const canApplyVerifiedStreamingTextAppend = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): boolean => {
    const cached = inputArguments.cached;
    const textAppend = inputArguments.textAppend;
    const assistantRevision = inputArguments.assistantRevision;
    if (inputArguments.patchType !== 'text-delta' || textAppend === null || assistantRevision === null || assistantRevision <= textAppend.baseAssistantRevision) {
        return false;
    }
    const cacheMatchesAppendBase = cached.renderMode === 'streaming' && cached.lastRenderedAssistantRevision === textAppend.baseAssistantRevision && cached.activeStreamTextRunKey !== null && cached.richTextProjection !== null && cached.lastAppliedActivityVisibleState?.textLength === textAppend.baseContentLength;
    if (!cacheMatchesAppendBase) {
        return false;
    }
    const content = inputArguments.message.content;
    if (!isString(content) || !content.endsWith(textAppend.textDelta)) {
        return false;
    }
    const expectedContentLength = textAppend.baseContentLength + textAppend.textDelta.length;
    if (content.length !== expectedContentLength || resolveStreamTimelineLength(inputArguments.message) !== textAppend.nextTimelineLength) {
        return false;
    }
    if (appendedTextIntroducesSoaiPathToken(content.slice(0, textAppend.baseContentLength), textAppend.textDelta)) {
        return false;
    }
    const streamSegments = cached.streamSegments;
    const streamText = cached.streamText;
    const streamTextSettled = cached.streamTextSettled;
    const streamTextTail = cached.streamTextTail;
    return isConnectedStreamingNode(target, streamSegments) && isConnectedStreamingNode(target, streamText) && isConnectedStreamingNode(target, streamTextSettled) && isConnectedStreamingNode(target, streamTextTail);
};

const renderVerifiedStreamingTextAppend = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): RenderStreamingMessageContentResult => {
    const textAppend = inputArguments.textAppend;
    const streamText = inputArguments.cached.streamText;
    const visibleState = inputArguments.cached.lastAppliedActivityVisibleState;
    if (textAppend === null || !(streamText instanceof HTMLElement) || visibleState === null) {
        throw new Error('Verified streaming text append state is unavailable');
    }
    const activeTextSync = syncVerifiedStreamingTextAppend({
        textDelta: textAppend.textDelta,
        messageArguments: inputArguments,
        streamText
    });
    if (activeTextSync.needsPostRender) {
        for (const postRenderTarget of activeTextSync.postRenderTargets) {
            inputArguments.messageManager.postRenderRequest(postRenderTarget, 'streamingText');
        }
    }
    let updatedMarkup = activeTextSync.updated;
    if (syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached })) {
        updatedMarkup = true;
    }
    inputArguments.cached.lastAppliedActivityVisibleState = {
        textLength: textAppend.baseContentLength + textAppend.textDelta.length,
        timelineLength: textAppend.nextTimelineLength,
        projectionFingerprint: visibleState.projectionFingerprint
    };
    return {
        handled: true,
        invalidatedCache: false,
        requiresActivityDurationReconcile: false,
        updatedMarkup,
        target
    };
};

const renderActiveStreamingMessageContent = (inputArguments: RenderStreamingMessageContentArguments, target: HTMLElement): RenderStreamingMessageContentResult => {
    if (canApplyVerifiedStreamingTextAppend(inputArguments, target)) {
        return renderVerifiedStreamingTextAppend(inputArguments, target);
    }
    const wasCollapsedLoading = inputArguments.cached.renderMode === 'collapsedLoading';
    let { streamSegments, streamText } = ensureStreamingStructure(target, inputArguments.cached);
    inputArguments.cached.renderMode = 'streaming';
    let updatedMarkup = false;

    const patchTimeline = inputArguments.patchType === 'text-delta' || inputArguments.patchType === 'timeline-activity' || inputArguments.patchType === 'both';
    const passivePatch = isPassiveStreamRenderPatchType(inputArguments.patchType);
    const hasStreamingText = messageHasStreamText(inputArguments.message);
    const requiresStreamingTextRecovery = passivePatch && streamText === null && hasStreamingText;
    const shouldResolveSegments = patchTimeline || wasCollapsedLoading || requiresStreamingTextRecovery || (passivePatch && (inputArguments.cached.richTextProjection?.source.length ?? 0) === 0 && hasStreamingText);
    const segments = shouldResolveSegments ? inputArguments.messageManager.resolveMessageContentSegments(inputArguments.message) : null;
    let activeTextRun: ActiveStreamingTextRun | null = null;
    let streamSegmentsNeedPostRender = false;
    let streamSegmentsPostRenderType: 'timeline' | 'full' = 'full';
    let streamSegmentsPostRenderTargets: HTMLElement[] = [];

    if (segments) {
        if (inputArguments.cached.messageRoot instanceof HTMLElement) {
            const spinnerActivityFlagsChanged = syncStreamingSpinnerActivityFlags(inputArguments.cached.messageRoot, segments);
            if (spinnerActivityFlagsChanged) {
                reconcileStreamingSpinnerStatusSubtree(inputArguments.cached.messageRoot);
            }
        }
        const timelineResult = patchTimelineChildren(inputArguments.message, inputArguments.cached, inputArguments.messageManager, streamSegments, segments);
        if (!timelineResult.supported) {
            return {
                handled: false,
                invalidatedCache: true,
                requiresActivityDurationReconcile: true,
                updatedMarkup: false,
                target
            };
        }
        activeTextRun = timelineResult.activeTextRun;
        if (timelineResult.updated) {
            updatedMarkup = true;
            ({ streamSegments, streamText } = ensureStreamingStructure(target, inputArguments.cached));
            if (inputArguments.patchType === 'timeline-activity') {
                streamSegmentsPostRenderType = 'timeline';
                streamSegmentsPostRenderTargets = timelineResult.changedElements;
            } else {
                streamSegmentsPostRenderType = 'full';
                streamSegmentsPostRenderTargets = [streamSegments];
            }
            streamSegmentsNeedPostRender = true;
        }
    }

    if (activeTextRun !== null || segments) {
        const activeTextSync = syncActiveStreamingTextRun({
            activeTextRun,
            messageArguments: inputArguments,
            streamText
        });
        if (activeTextSync.updated) {
            updatedMarkup = true;
        }
        if (activeTextSync.needsPostRender && (!streamSegmentsNeedPostRender || streamSegmentsPostRenderType === 'timeline')) {
            for (const target of activeTextSync.postRenderTargets) {
                inputArguments.messageManager.postRenderRequest(target, 'streamingText');
            }
        }
    }

    if (streamSegmentsNeedPostRender) {
        if (streamSegmentsPostRenderType === 'timeline') {
            if (streamSegmentsPostRenderTargets.length === 0) {
                inputArguments.messageManager.postRenderRequest(streamSegments, 'streamingTimeline');
            }
            for (const target of streamSegmentsPostRenderTargets) {
                inputArguments.messageManager.postRenderRequest(target, 'streamingTimeline');
                inputArguments.messageManager.postRenderRequest(target, 'streamingText');
            }
        } else {
            inputArguments.messageManager.postRender(streamSegments);
        }
    }

    if (syncStreamingMessagePassiveState({ message: inputArguments.message, target, messageManager: inputArguments.messageManager, cached: inputArguments.cached })) {
        updatedMarkup = true;
    }
    if (segments !== null) {
        inputArguments.cached.lastAppliedActivityVisibleState = resolveStreamActivityVisibleState(inputArguments.message);
    }

    return {
        handled: true,
        invalidatedCache: false,
        requiresActivityDurationReconcile: true,
        updatedMarkup,
        target
    };
};

export { renderActiveStreamingMessageContent };
