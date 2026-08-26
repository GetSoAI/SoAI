/* SoAI - Chat feature tool activity code diffs [frontend/assets/ts/features/chat/message/toolActivityCodeDiffs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ToolActivityCodeDiff } from '@features/chat/ChatTypes.ts';
import { resolveCodeDiffsFromToolResult } from '@core/chat/codeDiffParsing.ts';

const resolveToolResultCodeDiffs = (result: JsonValue | undefined): ToolActivityCodeDiff[] | null => {
    return resolveCodeDiffsFromToolResult(result);
};

export { resolveToolResultCodeDiffs };
