/* SoAI - Frontend assistant timeline wire serialization [frontend/assets/ts/core/realtime/eventcontracts/assistantTimelineSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import type { AssistantActivityState, AssistantEventTimelineItem, AssistantThinkingPhase, AssistantTimelinePayload, AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeActivity = (activity: AssistantActivityState): JsonObject => ({ status: activity.status, 'started_at_ms': activity.startedAtMs, 'duration_ms': activity.durationMs, ...(activity.reason !== undefined ? { reason: activity.reason } : {}), ...(activity.errorType !== undefined ? { 'error_type': activity.errorType } : {}) });

const serializeThinking = (thinking: AssistantThinkingPhase): JsonObject => ({
    'phase_id': thinking.phaseId,
    'sequence_index': thinking.sequenceIndex,
    'anchor_type': thinking.anchorType,
    ...(thinking.anchorCallId !== undefined ? { 'anchor_call_id': thinking.anchorCallId } : {}),
    ...(thinking.anchorPosition !== undefined ? { 'anchor_position': thinking.anchorPosition } : {}),
    text: thinking.text,
    'render_mode': thinking.renderMode,
    ...(thinking.prefaceText !== undefined ? { 'preface_text': thinking.prefaceText } : {}),
    'preface_complete': thinking.prefaceComplete,
    status: thinking.status,
    collapsed: thinking.collapsed,
    ...(thinking.durationMs !== undefined ? { 'duration_ms': thinking.durationMs } : {}),
    ...(thinking.startedAtMs !== undefined ? { 'started_at_ms': thinking.startedAtMs } : {})
});

const serializeAssistantTimelineTool = (tool: AssistantTimelineTool): JsonObject => ({
    'call_id': tool.callId,
    'tool_name': tool.toolName,
    status: tool.status,
    'sequence_index': tool.sequenceIndex,
    'message_index': tool.messageIndex,
    'content_index_before': tool.contentIndexBefore,
    'thinking_index_before': tool.thinkingIndexBefore,
    collapsed: tool.collapsed,
    ...(tool.inputArguments !== undefined ? { arguments: tool.inputArguments } : {}),
    ...(tool.result !== undefined ? { result: tool.result } : {}),
    ...(tool.error !== undefined ? { error: tool.error } : {}),
    ...(tool.durationMs !== undefined ? { 'duration_ms': tool.durationMs } : {}),
    ...(tool.startedAtMs !== undefined ? { 'started_at_ms': tool.startedAtMs } : {}),
    ...(tool.completedAtMs !== undefined ? { 'completed_at_ms': tool.completedAtMs } : {}),
    ...(tool.liveRevision !== undefined ? { 'live_revision': tool.liveRevision } : {}),
    ...(tool.lastLiveSequence !== undefined ? { 'last_live_sequence': tool.lastLiveSequence } : {}),
    ...(tool.lastLiveEventAtMs !== undefined ? { 'last_live_event_at_ms': tool.lastLiveEventAtMs } : {}),
    ...(tool.syncStatus !== undefined ? { 'sync_status': tool.syncStatus } : {}),
    ...(tool.thinkingDurationBeforeMs !== undefined ? { 'thinking_duration_before_ms': tool.thinkingDurationBeforeMs } : {}),
    ...(tool.assistantTurnAtMs !== undefined ? { 'assistant_turn_at_ms': tool.assistantTurnAtMs } : {}),
    ...(tool.modelVariantIndex !== undefined ? { 'model_variant_index': tool.modelVariantIndex } : {}),
    ...(tool.turnId !== undefined ? { 'turn_id': tool.turnId } : {}),
    ...(tool.iterationIndex !== undefined ? { 'iteration_index': tool.iterationIndex } : {}),
    ...(tool.codeDiffs !== undefined ? { 'code_diffs': tool.codeDiffs.map((entry) => ({ path: entry.path, operation: entry.operation, diff: entry.diff, truncated: entry.truncated })) } : {})
});

const serializeUsagePreview = (usage: TokenUsageSnapshot): JsonObject => ({
    'prompt_tokens': usage.promptTokens,
    'prompt_occupancy_tokens': usage.promptOccupancyTokens,
    'completion_tokens': usage.completionTokens,
    'context_completion_tokens': usage.contextCompletionTokens,
    'context_occupancy_tokens': usage.contextOccupancyTokens,
    'total_tokens': usage.totalTokens,
    'context_window_tokens': usage.contextWindowTokens,
    'completion_rate_tokens_per_second': usage.completionRateTokensPerSecond,
    source: usage.source,
    'context_window_unverified': usage.contextWindowUnverified,
    precision: usage.precision,
    'prompt_tokens_capped': usage.promptTokensCapped,
    'prompt_tokens_capped_reason': usage.promptTokensCappedReason,
    'preview_revision': usage.previewRevision
});

const serializeAssistantTimelinePayload = (payload: AssistantTimelinePayload): JsonObject => ({
    ...(payload.assistantAtMs !== undefined ? { 'assistant_at_ms': payload.assistantAtMs } : {}),
    ...(payload.assistantTurnAtMs !== undefined ? { 'assistant_turn_at_ms': payload.assistantTurnAtMs } : {}),
    ...(payload.assistantRevision !== undefined ? { 'assistant_revision': payload.assistantRevision } : {}),
    ...(payload.modelVariantIndex !== undefined ? { 'model_variant_index': payload.modelVariantIndex } : {}),
    ...(payload.delta !== undefined ? { delta: payload.delta } : {}),
    ...(payload.image !== undefined ? { image: { url: payload.image.url } } : {}),
    ...(payload.tool !== undefined ? { tool: serializeAssistantTimelineTool(payload.tool) } : {}),
    ...(payload.thinkingPhase !== undefined ? { 'thinking_phase': serializeThinking(payload.thinkingPhase) } : {}),
    ...(payload.loadingActivity !== undefined ? { 'loading_activity': serializeActivity(payload.loadingActivity) } : {}),
    ...(payload.processingActivity !== undefined ? { 'processing_activity': serializeActivity(payload.processingActivity) } : {}),
    ...(payload.waitForUserActivity !== undefined ? { 'wait_for_user_activity': serializeActivity(payload.waitForUserActivity) } : {}),
    ...(payload.usagePreview !== undefined ? { 'usage_preview': serializeUsagePreview(payload.usagePreview) } : {}),
    ...(payload.usage !== undefined ? { usage: payload.usage === null ? {} : { 'prompt_tokens': payload.usage.promptTokens, 'completion_tokens': payload.usage.completionTokens, 'total_tokens': payload.usage.totalTokens, 'usage_source': payload.usage.usageSource } } : {}),
    ...(payload.finishReason !== undefined ? { 'finish_reason': payload.finishReason } : {}),
    ...(payload.previewContract !== undefined ? { 'preview_contract': payload.previewContract } : {}),
    ...(payload.reason !== undefined ? { reason: payload.reason } : {}),
    ...(payload.code !== undefined ? { code: payload.code } : {}),
    ...(payload.message !== undefined ? { message: payload.message } : {}),
    ...(payload.referenceId !== undefined ? { 'reference_id': payload.referenceId } : {})
});

const serializeAssistantTimeline = (timeline: readonly AssistantEventTimelineItem[]): JsonObject[] => timeline.map((item) => ({ sequence: item.sequence, 'assistant_revision': item.assistantRevision, 'event_type': item.eventType, payload: serializeAssistantTimelinePayload(item.payload) }));

export { serializeAssistantTimeline, serializeAssistantTimelinePayload, serializeAssistantTimelineTool };
