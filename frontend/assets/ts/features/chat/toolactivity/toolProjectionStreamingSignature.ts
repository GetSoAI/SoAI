/* SoAI - Streaming visibility signatures for tool projections [frontend/assets/ts/features/chat/toolactivity/toolProjectionStreamingSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { resolveInlineToolHeaderQueryText } from '@features/chat/message/messageview/inlineToolActivityPayloadParsing.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';
import { resolveSubagentResultSignature } from '@features/chat/message/subagentResultSignature.ts';
import { resolveToolResultMediaStateSignature } from '@features/chat/toolactivity/toolMediaSignatures.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { toolRunningResultIsDetailHydrated } from '@features/chat/toolactivity/toolLiveResultPolicy.ts';

const buildInlineToolActivitySegment = (projection: ToolActivityItem): InlineToolActivitySegment => {
    const segment: InlineToolActivitySegment = {
        type: 'inline_tool_activity',
        callId: projection.callId,
        toolName: projection.toolName,
        status: projection.status,
        contentIndexBefore: projection.contentIndexBefore,
        assistantTurnAtMs: 0,
        modelVariantIndex: 0,
        collapsed: projection.collapsed !== false
    };
    if (projection.inputArguments !== undefined) {
        segment.inputArguments = projection.inputArguments;
    }
    if (projection.result !== undefined) {
        segment.result = projection.result;
    }
    if (projection.error !== undefined) {
        segment.error = projection.error;
    }
    if (projection.durationMs !== undefined) {
        segment.durationMs = projection.durationMs;
    }
    if (projection.startedAtMs !== undefined) {
        segment.startedAtMs = projection.startedAtMs;
    }
    if (projection.codeDiffs !== undefined) {
        segment.codeDiffs = projection.codeDiffs;
    }
    return segment;
};

const resolveJsonShapeSignature = (value: JsonValue | undefined): string => {
    if (value === undefined || value === null) {
        return 'none';
    }
    if (isString(value)) {
        return `str:${String(value.length)}`;
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
        return `${typeof value}:${String(value)}`;
    }
    if (isJsonArray(value)) {
        return `arr:${String(value.length)}`;
    }
    if (isJsonObject(value)) {
        return `obj:${String(Object.keys(value).length)}`;
    }
    return typeof value;
};

const resolveToolProjectionResultSignature = (tool: ToolActivityItem): string => {
    const result = tool.result;
    if (result === undefined || result === null) {
        return 'none';
    }
    if (isString(result)) {
        return `str:${String(result.length)}`;
    }
    if (!isJsonObject(result)) {
        return resolveJsonShapeSignature(result);
    }
    const output = result['output'];
    if (isString(output)) {
        return `output:${String(output.length)}`;
    }
    if (normalizeToolLeafName(tool.toolName) !== 'subagent_spawn' || (tool.status !== 'completed' && tool.status !== 'running')) {
        return `obj:${String(Object.keys(result).length)}:${resolveToolResultMediaStateSignature(result, { toolLeafName: tool.toolName })}`;
    }
    return resolveSubagentResultSignature(result);
};

const resolveToolProjectionHeaderPreviewText = (projection: ToolActivityItem): string => {
    return resolveInlineToolHeaderQueryText(buildInlineToolActivitySegment(projection));
};

const resolveToolProjectionVisibleStructureStreamingSignature = (projection: ToolActivityItem): string => {
    return [projection.callId, projection.toolName, projection.status, String(projection.sequenceIndex), String(projection.contentIndexBefore), String(projection.thinkingIndexBefore), projection.collapsed !== false ? '1' : '0', String(projection.startedAtMs ?? ''), String(projection.completedAtMs ?? ''), projection.durationMs === undefined ? '' : 'duration', isString(projection.error) ? String(projection.error.length) : '0'].join('|');
};

const resolveToolProjectionVisibleStreamingSignature = (projection: ToolActivityItem): string => {
    return [resolveToolProjectionVisibleStructureStreamingSignature(projection), resolveToolProjectionHeaderPreviewText(projection)].join('|');
};

const resolveToolProjectionActiveStreamingSignature = (projection: ToolActivityItem): string => {
    if (projection.status === 'running' && projection.collapsed !== false && toolRunningResultIsDetailHydrated(projection.toolName)) {
        return resolveToolProjectionVisibleStreamingSignature(projection);
    }
    return [resolveToolProjectionVisibleStreamingSignature(projection), String(projection.liveRevision ?? 0), String(projection.lastLiveSequence ?? -1), String(projection.lastLiveEventAtMs ?? 0), resolveJsonShapeSignature(projection.inputArguments), isJsonArray(projection.codeDiffs) ? String(projection.codeDiffs.length) : '0', resolveToolProjectionResultSignature(projection)].join('|');
};

export { resolveToolProjectionActiveStreamingSignature, resolveToolProjectionHeaderPreviewText, resolveToolProjectionVisibleStreamingSignature, resolveToolProjectionVisibleStructureStreamingSignature };
