/* SoAI - Chat feature stream message rendering contracts [frontend/assets/ts/features/chat/stream/streamMessageRenderingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatPostRenderCommit, ChatPostRenderRequestType } from '@features/chat/message/types.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import type { MessageRenderOptions, RenderedMessageTextContent } from '@features/chat/message/messageview/types.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { ActiveStreamRenderPatchType, StreamTextAppend } from '@features/chat/stream/streamRenderPatchType.ts';
import type { RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';

export interface StreamMessageManager {
    resolveMessageContentSegments(message: ChatMessage | null | undefined): MessageSegment[];
    renderSegments(segments: MessageSegment[], options?: MessageRenderOptions): string;
    renderActiveStreamMessageTextContent(message: ChatMessage): RenderedMessageTextContent;
    renderMarkdownContent(content: string, options?: { sortableTables?: boolean }): string;
    renderStreamingMarkdownContent(content: string): string;
    getWorkerRenderEpoch(): number;
    resolveRunningActivitySummary(message: ChatMessage, nowMs: number): RunningActivitySummary;
    getLoadingActivityCollapsedState(message: ChatMessage): boolean | null;
    isShowActivitiesEnabled(): boolean;
    postRender(container: Element | null): void;
    postRenderRequest(container: Element | null, type: ChatPostRenderRequestType, onCommitted?: ChatPostRenderCommit): void;
}

export interface RenderStreamingMessageContentArguments {
    message: ChatMessage;
    cached: StreamingElementCache;
    patchType: ActiveStreamRenderPatchType;
    assistantRevision: number | null;
    textAppend: StreamTextAppend | null;
    messageManager: StreamMessageManager;
}

export interface RenderStreamingMessageContentResult {
    handled: boolean;
    invalidatedCache: boolean;
    requiresActivityDurationReconcile: boolean;
    updatedMarkup: boolean;
    target: Element | null;
}
