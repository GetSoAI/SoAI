/* SoAI - Inline tool activity presentation policy for chat messages [frontend/assets/ts/features/chat/message/messageview/inlineToolActivityPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';
import { resolveToolResultCodeDiffs } from '@features/chat/message/toolActivityCodeDiffs.ts';
import { resolveToolActivityStatusLabel } from '@features/chat/message/toolActivityStatusLabel.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

interface InlineToolActivityPresentation {
    readonly toolLeafName: string;
    readonly suppressResult: boolean;
    readonly isTodoWrite: boolean;
    readonly isPlanWrite: boolean;
    readonly isSubagentSpawn: boolean;
    readonly hasCodeDiffs: boolean;
    readonly hasDetails: boolean;
    readonly statusSummaryText: string;
}

const STOP_CONVERSATION_TOOL_LEAF = 'stop_conversation';
const WAIT_TOOL_LEAF = 'wait';
const NON_EXPANDABLE_TOOL_LEAF_NAMES: ReadonlySet<string> = new Set([STOP_CONVERSATION_TOOL_LEAF, WAIT_TOOL_LEAF]);

const hasMeaningfulPayload = (payload: JsonValue | undefined): boolean => {
    if (payload === null || payload === undefined) {
        return false;
    }
    if (isString(payload)) {
        return payload.trim().length > 0;
    }
    if (isJsonArray(payload)) {
        return true;
    }
    if (isJsonObject(payload)) {
        return true;
    }
    return String(payload).trim().length > 0;
};

const resolveInlineToolActivityHasCodeDiffs = (segment: InlineToolActivitySegment): boolean => {
    if (isArray(segment.codeDiffs) && segment.codeDiffs.length > 0) {
        for (const entry of segment.codeDiffs) {
            if (!entry || !isString(entry.diff) || entry.diff.trim().length === 0) {
                continue;
            }
            return true;
        }
    }
    const resolved = resolveToolResultCodeDiffs(segment.result);
    return isArray(resolved) && resolved.length > 0;
};

const resolveInlineToolStatusSummaryText = (segment: InlineToolActivitySegment): string => {
    return resolveToolActivityStatusLabel(segment.status).trim();
};

const isInlineToolActivityExplicitlyNonExpandable = (toolLeafName: string): boolean => {
    return NON_EXPANDABLE_TOOL_LEAF_NAMES.has(toolLeafName);
};

const resolveInlineToolActivityPresentation = (segment: InlineToolActivitySegment): InlineToolActivityPresentation => {
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    const hasCodeDiffs = resolveInlineToolActivityHasCodeDiffs(segment);
    const suppressResult = toolLeafName === 'todo_write';
    const hasArguments = segment.inputArguments !== undefined && segment.inputArguments !== null && hasMeaningfulPayload(segment.inputArguments);
    const hasError = segment.status === 'error' && isString(segment.error) && segment.error.trim().length > 0;
    const hasResult = !suppressResult && !hasCodeDiffs && (segment.status === 'completed' || segment.status === 'running') && segment.result !== undefined;
    const statusSummaryText = resolveInlineToolStatusSummaryText(segment);
    const hasDetails = isInlineToolActivityExplicitlyNonExpandable(toolLeafName) ? false : hasArguments || hasCodeDiffs || hasResult || hasError || statusSummaryText.length > 0;
    return {
        toolLeafName,
        suppressResult,
        isTodoWrite: suppressResult,
        isPlanWrite: toolLeafName === 'plan_write',
        isSubagentSpawn: toolLeafName === 'subagent_spawn',
        hasCodeDiffs,
        hasDetails,
        statusSummaryText
    };
};

export { isInlineToolActivityExplicitlyNonExpandable, resolveInlineToolActivityPresentation, resolveInlineToolStatusSummaryText };
export type { InlineToolActivityPresentation };
