/* SoAI - Frontend agent code diff decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/codeDiffs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseCodeDiffArrayLenient, type ToolActivityCodeDiff } from '@core/chat/codeDiffParsing.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const parseAgentCodeDiffs = (value: JsonValue | undefined): ToolActivityCodeDiff[] | null => {
    return parseCodeDiffArrayLenient(value);
};

const parseAgentCodeDiffsFromRecord = (record: JsonObject, key: string = 'code_diffs'): ToolActivityCodeDiff[] | null => {
    return parseAgentCodeDiffs(record[key]);
};

export { parseAgentCodeDiffs, parseAgentCodeDiffsFromRecord };
