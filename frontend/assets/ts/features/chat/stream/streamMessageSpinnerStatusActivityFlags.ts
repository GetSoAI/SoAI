/* SoAI - Chat feature stream message spinner status activity flags [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusActivityFlags.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF } from '@features/chat/message/contextcompaction/detection.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE, STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';

const syncBooleanAttribute = (element: HTMLElement, attributeName: string, nextValue: boolean): boolean => {
    const nextAttributeValue = nextValue ? 'true' : 'false';
    if (element.getAttribute(attributeName) === nextAttributeValue) {
        return false;
    }
    element.setAttribute(attributeName, nextAttributeValue);
    return true;
};

const syncStreamingSpinnerActivityFlags = (messageRoot: HTMLElement, segments: readonly MessageSegment[]): boolean => {
    const actionsElement = resolveAssistantMessageParts(messageRoot)?.actions ?? null;
    if (!(actionsElement instanceof HTMLElement)) {
        return false;
    }
    let hasLoadingActivity = false;
    let hasRunningLoadingActivity = false;
    let hasRunningWaitActivity = false;
    let hasRunningContextCompactionActivity = false;
    for (const segment of segments) {
        if (segment.type === 'inline_loading_activity') {
            hasLoadingActivity = true;
            if (segment.status === 'running') {
                hasRunningLoadingActivity = true;
            }
            continue;
        }
        if (segment.type === 'inline_tool_activity' && segment.status === 'running') {
            const toolLeafName = normalizeToolLeafName(segment.toolName);
            if (toolLeafName === 'wait') {
                hasRunningWaitActivity = true;
            }
            if (toolLeafName === CONTEXT_COMPACTION_TOOL_LEAF) {
                hasRunningContextCompactionActivity = true;
            }
        }
    }
    let changed = false;
    if (syncBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_LOADING_ACTIVITY_ATTRIBUTE, hasLoadingActivity)) {
        changed = true;
    }
    if (syncBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_RUNNING_LOADING_ACTIVITY_ATTRIBUTE, hasRunningLoadingActivity)) {
        changed = true;
    }
    if (syncBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_RUNNING_WAIT_ACTIVITY_ATTRIBUTE, hasRunningWaitActivity)) {
        changed = true;
    }
    if (syncBooleanAttribute(actionsElement, STREAM_SPINNER_HAS_RUNNING_CONTEXT_COMPACTION_ACTIVITY_ATTRIBUTE, hasRunningContextCompactionActivity)) {
        changed = true;
    }
    return changed;
};

export { syncStreamingSpinnerActivityFlags };
