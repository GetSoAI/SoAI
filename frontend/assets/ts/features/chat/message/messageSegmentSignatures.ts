/* SoAI - Message segment render signatures [frontend/assets/ts/features/chat/message/messageSegmentSignatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import type { InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveInlineActivityDisplayDurationMs, resolveInlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { resolveInlineToolHeaderQueryText } from '@features/chat/message/messageview/inlineToolActivityPayloadParsing.ts';
import { resolveSubagentToolResultModel } from '@features/chat/message/messageview/subagentStreamSegments.ts';
import { resolvePayloadRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import { resolveToolImageDescriptor } from '@features/chat/toolactivity/toolImagePayload.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { resolveToolResultMediaStateSignature } from '@features/chat/toolactivity/toolMediaSignatures.ts';
import { toolRunningResultIsDetailHydrated } from '@features/chat/toolactivity/toolLiveResultPolicy.ts';
import { resolveToolResultPresentation } from '@features/chat/toolactivity/toolOutputPresentation.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

type DurationSignatureSegment = InlineToolActivitySegment | InlineThinkingActivitySegment | InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;

const requireSignatureSequence = (segment: MessageSegment, context: string): number => {
    if (!('signatureSequence' in segment)) {
        throw new Error(`${context} requires segment.signature_sequence`);
    }
    const value = segment.signatureSequence;
    if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        throw new Error(`${context} requires segment.signature_sequence`);
    }
    return value;
};

const resolveDisplayDurationSignature = (segment: DurationSignatureSegment, nowMs: number): string => {
    const display = resolveInlineActivityDisplayDurationMs(resolveInlineActivityDurationArguments(segment, nowMs));
    return String(display ?? '');
};

const resolveRunningDurationSourceSignature = (segment: DurationSignatureSegment): string => (segment.durationMs === undefined ? '' : 'duration');

const isRunningInlineActivitySegment = (segment: MessageSegment): segment is DurationSignatureSegment => {
    if (segment.type !== 'inline_tool_activity' && segment.type !== 'inline_thinking_activity' && segment.type !== 'inline_loading_activity' && segment.type !== 'inline_processing_activity' && segment.type !== 'inline_wait_for_user_activity') {
        return false;
    }
    return segment.status === 'running';
};

const resolveStringContentSignature = (value: string): string => {
    return stableJsonStringify(['text', value.length, value]);
};

const resolveInlineToolActivityHeaderPreviewSignature = (segment: InlineToolActivitySegment): string => {
    return resolveStringContentSignature(resolveInlineToolHeaderQueryText(segment));
};

const resolveSubagentSegmentsSignature = (segments: MessageSegment[], nowMs: number): string => {
    const signatures: string[] = [];
    for (const segment of segments) {
        signatures.push(resolveSegmentSignature(segment, nowMs));
    }
    return signatures.join(',');
};

const resolveSegmentSignature = (segment: MessageSegment, nowMs: number): string => {
    if (segment.type === 'inline_tool_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_tool_activity');
        return ['inline_tool_activity', segment.callId, String(segment.contentIndexBefore), String(signatureSequence), segment.status, String(segment.collapsed ? 1 : 0), String(segment.startedAtMs ?? ''), resolveDisplayDurationSignature(segment, nowMs), resolveInlineToolActivityHeaderPreviewSignature(segment)].join('|');
    }
    if (segment.type === 'inline_thinking_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_thinking_activity');
        return ['inline_thinking_activity', segment.callId, String(segment.timelineSequenceIndex), String(segment.contentIndexBefore), String(signatureSequence), segment.status, String(segment.collapsed ? 1 : 0), String(segment.startedAtMs ?? ''), resolveDisplayDurationSignature(segment, nowMs)].join('|');
    }
    if (segment.type === 'inline_action_update') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_action_update');
        return ['inline_action_update', segment.callId, String(segment.timelineSequenceIndex), String(segment.contentIndexBefore), String(signatureSequence), segment.text].join('|');
    }
    if (segment.type === 'inline_loading_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_loading_activity');
        return ['inline_loading_activity', String(signatureSequence), segment.status, String(segment.startedAtMs), resolveDisplayDurationSignature(segment, nowMs)].join('|');
    }
    if (segment.type === 'inline_processing_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_processing_activity');
        return ['inline_processing_activity', String(signatureSequence), segment.status, String(segment.startedAtMs), resolveDisplayDurationSignature(segment, nowMs)].join('|');
    }
    if (segment.type === 'inline_wait_for_user_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_wait_for_user_activity');
        return ['inline_wait_for_user_activity', String(signatureSequence), segment.status, String(segment.startedAtMs), resolveDisplayDurationSignature(segment, nowMs)].join('|');
    }
    if (segment.type === 'tool_call') {
        return ['tool_call', String(segment.id ?? ''), String(segment.name ?? '')].join('|');
    }
    if (segment.type === 'image') {
        const signatureSequence = typeof segment.signatureSequence === 'number' && Number.isFinite(segment.signatureSequence) && Number.isInteger(segment.signatureSequence) && segment.signatureSequence >= 0 ? segment.signatureSequence : null;
        return ['image', String(signatureSequence ?? ''), segment.imageUrl, segment.title].join('|');
    }
    if (segment.type === 'text') {
        if (typeof segment.timelineSequence === 'number' && Number.isFinite(segment.timelineSequence) && Number.isInteger(segment.timelineSequence) && segment.timelineSequence >= 0) {
            const signatureSequence = requireSignatureSequence(segment, 'text timeline segment');
            return ['text', 'timeline', String(segment.timelineSequence), String(signatureSequence), resolveStringContentSignature(segment.value)].join('|');
        }
        return ['text', resolveStringContentSignature(segment.value)].join('|');
    }
    if (segment.type === 'thinking') {
        return ['thinking', resolveStringContentSignature(segment.value)].join('|');
    }
    if (segment.type === 'soai_file') {
        return stableJsonStringify(['soai_file', segment.attachmentId, segment.fileId, segment.filename, segment.mimeType, segment.sizeBytes, segment.previewType, segment.attachmentRevision, segment.createdAtMs]);
    }
    if (segment.type === 'soai_path') {
        return stableJsonStringify(['soai_path', segment.title, segment.virtualPath, segment.rootFingerprint, segment.entryType, serializeSoaiPathContentPart(segment.contentPart), segment.previewType ?? '', segment.mimeType ?? '', segment.sizeBytes ?? null]);
    }
    if (segment.type === 'soai_knowledge') {
        return stableJsonStringify(['soai_knowledge', segment.knowledgeAttachmentId, segment.summaryId, segment.sourceType, segment.operationType, segment.title, segment.totalCount, segment.visibleCount, segment.hiddenCount, segment.statusCounts, segment.attachmentRevision, segment.firstEventId, segment.lastEventId, segment.createdAtMs, segment.finalizedAtMs]);
    }
    if (segment.type === 'soai_file_unavailable') {
        return stableJsonStringify(['soai_file_unavailable', segment.filename, segment.mimeType, segment.sizeBytes, segment.previewType, segment.reason]);
    }
    if (segment.type === 'soai_knowledge_unavailable') {
        return stableJsonStringify(['soai_knowledge_unavailable', segment.title, segment.sourceType, segment.reason]);
    }
    throw new Error('Unsupported message segment type for render signature');
};

const resolveRunningInlineActivitySignature = (segment: DurationSignatureSegment): string => {
    const durationSignature = resolveRunningDurationSourceSignature(segment);
    if (segment.type === 'inline_tool_activity') {
        return ['inline_tool_activity', segment.callId, String(segment.contentIndexBefore), String(requireSignatureSequence(segment, 'inline_tool_activity streaming signature')), segment.status, String(segment.collapsed ? 1 : 0), String(segment.startedAtMs ?? ''), durationSignature, resolveInlineToolActivityHeaderPreviewSignature(segment)].join('|');
    }
    if (segment.type === 'inline_thinking_activity') {
        return ['inline_thinking_activity', segment.callId, String(segment.timelineSequenceIndex), String(segment.contentIndexBefore), String(requireSignatureSequence(segment, 'inline_thinking_activity streaming signature')), segment.status, String(segment.collapsed ? 1 : 0), String(segment.startedAtMs ?? ''), durationSignature].join('|');
    }
    if (segment.type === 'inline_loading_activity') {
        return ['inline_loading_activity', String(requireSignatureSequence(segment, 'inline_loading_activity streaming signature')), segment.status, String(segment.startedAtMs), durationSignature].join('|');
    }
    if (segment.type === 'inline_processing_activity') {
        return ['inline_processing_activity', String(requireSignatureSequence(segment, 'inline_processing_activity streaming signature')), segment.status, String(segment.startedAtMs), durationSignature].join('|');
    }
    return ['inline_wait_for_user_activity', String(requireSignatureSequence(segment, 'inline_wait_for_user_activity streaming signature')), segment.status, String(segment.startedAtMs), durationSignature].join('|');
};

const resolveTimelineBaseSegmentSignature = (segment: MessageSegment, nowMs: number): string => (isRunningInlineActivitySegment(segment) ? resolveRunningInlineActivitySignature(segment) : resolveSegmentSignature(segment, nowMs));

const resolveInlineActivityDetailsSignature = (segment: MessageSegment, nowMs: number): string => {
    if (segment.type === 'inline_tool_activity') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_tool_activity details');
        const callId = segment.callId;
        const startedAt = segment.startedAtMs ?? null;
        const hasArguments = segment.inputArguments !== undefined && segment.inputArguments !== null;
        const codeDiffCount = isArray(segment.codeDiffs) ? segment.codeDiffs.length : 0;
        const errorLen = isString(segment.error) ? segment.error.length : 0;

        let resultTag = 'none';
        const toolLeafName = normalizeToolLeafName(segment.toolName);
        const result = segment.result;
        if (toolLeafName === 'subagent_spawn' && (segment.status === 'completed' || segment.status === 'running') && result !== undefined && result !== null) {
            const assistantIdentity = resolveAssistantVariantIdentity({
                assistantTurnTimestamp: segment.assistantTurnAtMs,
                modelVariantIndex: segment.modelVariantIndex
            });
            if (assistantIdentity === null) {
                throw new Error('Subagent tool activity segment is missing assistant comparison identity.');
            }
            const parsed = resolveSubagentToolResultModel(result, callId, {
                assistantTurnTimestamp: assistantIdentity.assistantTurnTimestamp,
                modelVariantIndex: assistantIdentity.modelVariantIndex
            });
            const subagentStatus = isString(parsed.statusRecord['status']) ? parsed.statusRecord['status'] : '';
            const contentSignature = resolveSubagentSegmentsSignature(parsed.streamSegments, nowMs);
            resultTag = ['subagent', subagentStatus, resolveStringContentSignature(parsed.resultText), String(parsed.streamSegments.length), contentSignature].join('|');
        }
        if (resultTag === 'none' && isString(result)) {
            resultTag = `str:${resolveStringContentSignature(result)}`;
        } else if (resultTag === 'none' && isNumber(result) && Number.isFinite(result)) {
            resultTag = `num:${String(result)}`;
        } else if (resultTag === 'none' && isPlainObject(result)) {
            if (toolLeafName === 'subagent_spawn') {
                resultTag = `obj:${String(Object.keys(result).length)}`;
            } else {
                const requestRecord = segment.inputArguments === undefined || segment.inputArguments === null ? null : resolvePayloadRecord(segment.inputArguments);
                const imageDescriptor = resolveToolImageDescriptor(result, { toolLeafName });
                const consumedImageKeys = imageDescriptor === null ? [] : imageDescriptor.consumedKeys;
                const presentation = resolveToolResultPresentation({
                    toolLeafName,
                    resultRecord: result,
                    requestRecord,
                    consumedImageKeys
                });
                resultTag = [presentation.signature, resolveToolResultMediaStateSignature(result, { toolLeafName })].join('|');
            }
        }

        const signatureTag = segment.status === 'running' && !toolRunningResultIsDetailHydrated(segment.toolName) ? '' : `sig:${String(signatureSequence)}`;
        return ['inline_tool_activity_details', callId, String(segment.status), String(segment.collapsed ? 1 : 0), String(startedAt ?? ''), signatureTag, hasArguments ? 'args:1' : 'args:0', `diffs:${String(codeDiffCount)}`, `err:${String(errorLen)}`, resultTag].filter((value) => value.length > 0).join('|');
    }
    if (segment.type === 'inline_thinking_activity') {
        const callId = segment.callId;
        const startedAt = segment.startedAtMs ?? null;
        const textSignature = isString(segment.text) ? resolveStringContentSignature(segment.text) : 'text:0';
        return ['inline_thinking_activity_details', callId, String(segment.timelineSequenceIndex), String(segment.contentIndexBefore), String(segment.status), String(segment.collapsed ? 1 : 0), String(startedAt ?? ''), textSignature].join('|');
    }
    if (segment.type === 'inline_action_update') {
        const signatureSequence = requireSignatureSequence(segment, 'inline_action_update details');
        return ['inline_action_update_details', segment.callId, String(segment.timelineSequenceIndex), String(segment.contentIndexBefore), String(signatureSequence), segment.text].join('|');
    }
    return resolveSegmentSignature(segment, nowMs);
};

export { resolveInlineActivityDetailsSignature, resolveInlineToolActivityHeaderPreviewSignature, resolveSegmentSignature, resolveTimelineBaseSegmentSignature };
