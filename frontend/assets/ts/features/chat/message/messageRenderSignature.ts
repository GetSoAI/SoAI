/* SoAI - Chat feature message render signature [frontend/assets/ts/features/chat/message/messageRenderSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { isJsonArray, isJsonObject } from '@core/types/jsonValues.ts';
import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { resolveContextCompactionBoundaryRenderModel } from '@features/chat/message/contextcompaction/renderModel.ts';
import { resolveAssistantMessageRevisionNumberFromMessage } from '@features/chat/message/messageSegmentsResolution.ts';
import { resolveSubagentResultSignature } from '@features/chat/message/subagentResultSignature.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { resolveToolProjectionActiveStreamingSignature } from '@features/chat/toolactivity/toolProjectionStreamingSignature.ts';

type ChatMessageRenderSignatureMode = 'full' | 'active-streaming';

const resolveComparisonTurnSignatureValue = (comparisonTurn: ChatComparisonTurnRenderModel | null): string => {
    if (!comparisonTurn) {
        return '';
    }
    return [comparisonTurn.assistantTurnTimestamp, comparisonTurn.modelVariantIndex, comparisonTurn.variantCount, comparisonTurn.invalidReason ?? ''].join(':');
};

const resolveTextSignature = (type: string, value: string): string => `${type}:${String(value.length)}:${formatHashSignature(value)}`;

const resolveJsonShapeSignature = <TValue>(value: TValue): string => {
    if (value === undefined || value === null) {
        return 'none';
    }
    if (isString(value)) {
        return resolveTextSignature('str', value);
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
        return `${typeof value}:${String(value)}`;
    }
    if (isJsonArray(value)) {
        return `arr:${formatHashSignature(value)}`;
    }
    if (isJsonObject(value)) {
        return `obj:${formatHashSignature(value)}`;
    }
    return typeof value;
};

const resolveContentSignature = (message: ChatMessage): string => {
    const content = message.content;
    if (typeof content === 'string') {
        return resolveTextSignature('str', content);
    }
    if (content === undefined || content === null) {
        return '0:0';
    }
    return resolveJsonShapeSignature(content);
};

const resolveTimelineSignature = (message: ChatMessage): string => {
    const timeline = message.assistantEventTimeline;
    if (!Array.isArray(timeline) || timeline.length === 0) {
        return '0:0';
    }
    return `timeline:${String(timeline.length)}:${String(resolveAssistantMessageRevisionNumberFromMessage(message) ?? 0)}:${formatHashSignature(timeline)}`;
};

const resolveResultSignature = (tool: ToolActivityItem): string => {
    const result = tool.result;
    if (result === undefined || result === null) {
        return '0';
    }
    if (typeof result === 'string') {
        return resolveTextSignature('str', result);
    }
    if (isJsonObject(result)) {
        const output = result['output'];
        const status = result['status'];
        if (isString(output)) {
            return resolveTextSignature('output', output);
        }
        if (normalizeToolLeafName(tool.toolName) !== 'subagent_spawn' || (tool.status !== 'completed' && tool.status !== 'running')) {
            return ['obj', resolveJsonShapeSignature(status), resolveJsonShapeSignature(result)].join(':');
        }
        return resolveSubagentResultSignature(result);
    }
    return resolveJsonShapeSignature(result);
};

const resolveToolCallsSignature = (message: ChatMessage): string => {
    const toolCalls = message.toolCalls;
    if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
        return '0';
    }
    return toolCalls.map((toolCall) => [String(toolCall.id ?? ''), String(toolCall.type ?? ''), resolveJsonShapeSignature(toolCall.function ?? null)].join(':')).join('|');
};

const resolveToolProjectionSignature = (message: ChatMessage): string => {
    const projections = message.toolCallProjections;
    if (!Array.isArray(projections) || projections.length === 0) {
        return '';
    }
    return projections.map((tool) => [tool.callId, tool.status, String(tool.liveRevision ?? 0), String(tool.lastLiveSequence ?? -1), String(tool.lastLiveEventAtMs ?? 0), String(tool.syncStatus ?? ''), String(tool.startedAtMs ?? 0), String(tool.completedAtMs ?? 0), String(tool.durationMs ?? 0), isString(tool.error) ? resolveTextSignature('err', tool.error) : '0', resolveResultSignature(tool)].join(':')).join('|');
};

const resolveActiveStreamingToolProjectionSignature = (message: ChatMessage): string => {
    const projections = message.toolCallProjections;
    if (!Array.isArray(projections) || projections.length === 0) {
        return '';
    }
    return projections.map((tool) => resolveToolProjectionActiveStreamingSignature(tool)).join('|');
};

const resolveContextCompactionBoundarySignature = (message: ChatMessage): string => {
    const renderModel = resolveContextCompactionBoundaryRenderModel(message);
    return [renderModel.isBoundary ? '1' : '0', renderModel.renderActions ? '1' : '0', renderModel.rootClassName, renderModel.contentClassName].join(':');
};

const resolveChatMessageRenderSignatureByMode = (message: ChatMessage, comparisonTurn: ChatComparisonTurnRenderModel | null, mode: ChatMessageRenderSignatureMode): string => {
    const base = [message.role, String(message.timestamp ?? 0), String(message.assistantTurnAtMs ?? 0), String(message.modelVariantIndex ?? 0), resolveComparisonTurnSignatureValue(comparisonTurn), message.modelId ?? '', message.soaiMessageType ?? '', message.errorCode ?? '', resolveJsonShapeSignature(message.soaiCompaction ?? null), resolveContextCompactionBoundarySignature(message)];
    if (mode === 'active-streaming') {
        return [...base, resolveActiveStreamingToolProjectionSignature(message)].join('|');
    }
    return [
        ...base,
        resolveContentSignature(message),
        String(message.finishReason ?? ''),
        String(message.promptTokens ?? 0),
        String(message.completionTokens ?? 0),
        String(message.totalTokens ?? 0),
        String(message.generationLatencyMs ?? 0),
        String(message.generationSpeedTokensPerSec ?? 0),
        String(message.thinkingTailDurationMs ?? 0),
        resolveTimelineSignature(message),
        resolveToolProjectionSignature(message),
        resolveToolCallsSignature(message),
        resolveJsonShapeSignature(message.inlineThinkingCollapsedByCallId ?? null),
        resolveJsonShapeSignature(message.inlineToolCollapsedByCallId ?? null),
        resolveJsonShapeSignature(message.usage ?? null),
        resolveJsonShapeSignature(message.attachments ?? null),
        resolveJsonShapeSignature(message.images ?? null),
        resolveJsonShapeSignature(message.documents ?? null),
        resolveJsonShapeSignature(message.message ?? null),
        resolveJsonShapeSignature(message.streamStatusPreviewText ?? null),
        resolveJsonShapeSignature(message.streamStatusPreviewCooldownMs ?? null)
    ].join('|');
};

const resolveChatMessageRenderSignature = (message: ChatMessage, comparisonTurn: ChatComparisonTurnRenderModel | null): string => resolveChatMessageRenderSignatureByMode(message, comparisonTurn, 'full');

const resolveChatMessageRenderCacheSignature = (domId: string, message: ChatMessage, comparisonTurn: ChatComparisonTurnRenderModel | null): string => `${domId}|${resolveChatMessageRenderSignature(message, comparisonTurn)}`;

const resolveChatMessageActiveStreamingSignature = (message: ChatMessage, comparisonTurn: ChatComparisonTurnRenderModel | null): string => resolveChatMessageRenderSignatureByMode(message, comparisonTurn, 'active-streaming');

export { resolveChatMessageActiveStreamingSignature, resolveChatMessageRenderCacheSignature, resolveChatMessageRenderSignature };
