/* SoAI - Chat feature stream message rich text [frontend/assets/ts/features/chat/stream/streamMessageRichText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeMultilineInput } from '@core/richtextrenderer/mappers.ts';
import { resolveStreamingMutableSource, streamingMarkdownAppendRequiresCanonicalRender } from '@core/richtextrenderer/streamingBlockProjection.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { StreamMessageManager } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { patchStreamingPlainTextTail, renderStreamingRichTextRegion } from '@features/chat/stream/streamRichTextRegionRendering.ts';

type StreamRichTextUpdateResult = {
    updated: boolean;
    needsPostRender: boolean;
    postRenderTargets: HTMLElement[];
};

const STREAM_RICH_TEXT_DELTA_CHARS = 768;

const resolveStreamingAppendText = (inputArguments: { cached: StreamingElementCache; text: string; streamTextRunKey: string }): string => {
    if (inputArguments.cached.activeStreamTextRunKey !== inputArguments.streamTextRunKey) {
        return inputArguments.text;
    }
    return inputArguments.text.slice(inputArguments.cached.richTextProjection?.source.length ?? 0);
};

const canPatchStreamingPlainText = (inputArguments: { cached: StreamingElementCache; text: string; appendText: string; streamTextRunKey: string; renderEpoch: number }): boolean => {
    const projection = inputArguments.cached.richTextProjection;
    if (projection === null || inputArguments.cached.richTextRenderEpoch !== inputArguments.renderEpoch || !projection.plainTextAppendSafe) {
        return false;
    }
    if (inputArguments.cached.activeStreamTextRunKey !== inputArguments.streamTextRunKey || !inputArguments.text.startsWith(projection.source)) {
        return false;
    }
    if (inputArguments.text.length - projection.source.length >= STREAM_RICH_TEXT_DELTA_CHARS) {
        return false;
    }
    return !streamingMarkdownAppendRequiresCanonicalRender(resolveStreamingMutableSource(projection), inputArguments.appendText);
};

export const updateStreamRichTextFromText = (inputArguments: { text: string; streamTextRunKey: string; cached: StreamingElementCache; messageManager: StreamMessageManager }): StreamRichTextUpdateResult => {
    const { streamTextRunKey, cached, messageManager } = inputArguments;
    const text = normalizeMultilineInput(inputArguments.text);
    const appendText = resolveStreamingAppendText({ cached, text, streamTextRunKey });
    const renderEpoch = messageManager.getWorkerRenderEpoch();
    const canPatchPlainText = canPatchStreamingPlainText({ cached, text, appendText, streamTextRunKey, renderEpoch });
    cached.activeStreamTextRunKey = streamTextRunKey;
    cached.streamText?.setAttribute('data-stream-rich-text', 'true');
    if (canPatchPlainText) {
        const tailPatch = patchStreamingPlainTextTail(cached, appendText);
        if (tailPatch.patched) {
            const projection = cached.richTextProjection;
            if (projection === null) {
                throw new Error('Streaming rich-text projection disappeared during an incremental append');
            }
            cached.richTextProjection = { ...projection, source: text };
            return { updated: tailPatch.updated, needsPostRender: false, postRenderTargets: [] };
        }
    }
    const renderResult = renderStreamingRichTextRegion({
        cached,
        messageManager,
        source: text
    });
    return {
        updated: renderResult.updated,
        needsPostRender: renderResult.postRenderTargets.length > 0,
        postRenderTargets: renderResult.postRenderTargets
    };
};
