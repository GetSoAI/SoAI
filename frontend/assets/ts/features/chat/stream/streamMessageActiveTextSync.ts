/* SoAI - Active streaming text synchronization [frontend/assets/ts/features/chat/stream/streamMessageActiveTextSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { updateStreamRichTextFromText } from '@features/chat/stream/streamMessageRichText.ts';
import { syncStreamingTextVisibility } from '@features/chat/stream/streamMessageRenderState.ts';
import type { RenderStreamingMessageContentArguments } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { resetTextTrackingState } from '@features/chat/stream/streamMessageStreamingStructure.ts';
import type { ActiveStreamingTextRun } from '@features/chat/stream/streamMessageTimelineChildren.ts';

type ActiveStreamingTextSyncResult = {
    needsPostRender: boolean;
    postRenderTargets: HTMLElement[];
    streamText: HTMLElement | null;
    updated: boolean;
};

const syncMissingActiveStreamingTextRun = (inputArguments: RenderStreamingMessageContentArguments): ActiveStreamingTextSyncResult => {
    if (inputArguments.cached.activeStreamTextRunKey === null && (inputArguments.cached.richTextProjection?.source.length ?? 0) === 0) {
        return { needsPostRender: false, postRenderTargets: [], streamText: null, updated: false };
    }
    resetTextTrackingState(inputArguments.cached);
    inputArguments.cached.activeStreamTextRunKey = null;
    const streamText = inputArguments.cached.streamText;
    if (streamText instanceof HTMLElement && syncStreamingTextVisibility(streamText, false)) {
        return { needsPostRender: false, postRenderTargets: [], streamText, updated: true };
    }
    return { needsPostRender: false, postRenderTargets: [], streamText: streamText instanceof HTMLElement ? streamText : null, updated: false };
};

const syncPresentActiveStreamingTextRun = (inputArguments: RenderStreamingMessageContentArguments, activeTextRun: ActiveStreamingTextRun, streamText: HTMLElement): ActiveStreamingTextSyncResult => {
    let updated = false;
    const shouldRevealStreamText = activeTextRun.text.trim().length > 0 || (inputArguments.cached.streamTextSettled?.textContent?.trim().length ?? 0) > 0;
    if (syncStreamingTextVisibility(streamText, shouldRevealStreamText)) {
        updated = true;
    }
    const richTextResult = updateStreamRichTextFromText({
        text: activeTextRun.text,
        streamTextRunKey: activeTextRun.key,
        cached: inputArguments.cached,
        messageManager: inputArguments.messageManager
    });
    return {
        needsPostRender: richTextResult.needsPostRender,
        postRenderTargets: richTextResult.postRenderTargets,
        streamText,
        updated: updated || richTextResult.updated
    };
};

const syncActiveStreamingTextRun = (inputArguments: { activeTextRun: ActiveStreamingTextRun | null; messageArguments: RenderStreamingMessageContentArguments; streamText: HTMLElement | null }): ActiveStreamingTextSyncResult => {
    if (inputArguments.activeTextRun === null) {
        return syncMissingActiveStreamingTextRun(inputArguments.messageArguments);
    }
    if (!(inputArguments.streamText instanceof HTMLElement)) {
        throw new Error('Active streaming text slot is unavailable for active text run');
    }
    return syncPresentActiveStreamingTextRun(inputArguments.messageArguments, inputArguments.activeTextRun, inputArguments.streamText);
};

const syncVerifiedStreamingTextAppend = (inputArguments: { textDelta: string; messageArguments: RenderStreamingMessageContentArguments; streamText: HTMLElement }): ActiveStreamingTextSyncResult => {
    const cached = inputArguments.messageArguments.cached;
    const streamTextRunKey = cached.activeStreamTextRunKey;
    if (streamTextRunKey === null) {
        throw new Error('Verified streaming text append requires an active text run');
    }
    const projection = cached.richTextProjection;
    if (projection === null) {
        throw new Error('Verified streaming text append requires a rich-text projection');
    }
    const text = `${projection.source}${inputArguments.textDelta}`;
    let updated = syncStreamingTextVisibility(inputArguments.streamText, text.trim().length > 0);
    const richTextResult = updateStreamRichTextFromText({
        text,
        streamTextRunKey,
        cached,
        messageManager: inputArguments.messageArguments.messageManager
    });
    if (richTextResult.updated) {
        updated = true;
    }
    return {
        needsPostRender: richTextResult.needsPostRender,
        postRenderTargets: richTextResult.postRenderTargets,
        streamText: inputArguments.streamText,
        updated
    };
};

export { syncActiveStreamingTextRun, syncVerifiedStreamingTextAppend };
export type { ActiveStreamingTextSyncResult };
