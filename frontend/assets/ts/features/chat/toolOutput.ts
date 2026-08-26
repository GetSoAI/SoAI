/* SoAI - Chat feature tool output [frontend/assets/ts/features/chat/toolOutput.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const MAX_TOOL_OUTPUT_CHARS = 2_000_000;

export const appendCappedToolOutput = (baseOutput: string, delta: string): string => {
    const nextOutput = baseOutput + delta;
    if (nextOutput.length <= MAX_TOOL_OUTPUT_CHARS) {
        return nextOutput;
    }
    return nextOutput.slice(nextOutput.length - MAX_TOOL_OUTPUT_CHARS);
};
