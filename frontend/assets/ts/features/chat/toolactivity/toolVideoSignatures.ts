/* SoAI - Tool video payload state signatures [frontend/assets/ts/features/chat/toolactivity/toolVideoSignatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { collectToolVideoStateSignatures, resolveOmittedToolVideoDescriptor, resolveToolVideoDescriptor, resolveToolVideoHydrationRank } from '@features/chat/toolactivity/toolVideoPayload.ts';

interface ToolVideoPayloadCounts {
    inlineChars: number;
    inlineCount: number;
    omittedChars: number;
    omittedCount: number;
    signatures: string[];
}

const emptyCounts = (): ToolVideoPayloadCounts => ({
    inlineChars: 0,
    inlineCount: 0,
    omittedChars: 0,
    omittedCount: 0,
    signatures: []
});

const countToolVideoPayloadState = (value: JsonValue | undefined): ToolVideoPayloadCounts => {
    const counts = emptyCounts();
    const inline = resolveToolVideoDescriptor(value);
    if (inline !== null) {
        counts.inlineCount += 1;
        counts.inlineChars += inline.payload.videoBase64.length;
    }
    const omitted = resolveOmittedToolVideoDescriptor(value);
    if (omitted !== null) {
        counts.omittedCount += 1;
        counts.omittedChars += omitted.totalChars ?? 0;
    }
    counts.signatures.push(...collectToolVideoStateSignatures(value));
    return counts;
};

const hasToolResultInlineVideoBase64 = (value: JsonValue | undefined): boolean => resolveToolVideoDescriptor(value) !== null;

const hasToolResultOmittedInlineVideoBase64 = (value: JsonValue | undefined): boolean => resolveOmittedToolVideoDescriptor(value) !== null;

const resolveToolResultVideoHydrationRank = (value: JsonValue | undefined): number => resolveToolVideoHydrationRank(value);

const resolveToolResultVideoStateSignature = (value: JsonValue | undefined): string => {
    const counts = countToolVideoPayloadState(value);
    const sortedSignatures = counts.signatures.sort((left, right) => left.localeCompare(right, 'en'));
    return [`inline-video:${String(counts.inlineCount)}:${String(counts.inlineChars)}`, `omitted-video:${String(counts.omittedCount)}:${String(counts.omittedChars)}`, sortedSignatures.join('|')].join('|');
};

export { hasToolResultInlineVideoBase64, hasToolResultOmittedInlineVideoBase64, resolveToolResultVideoHydrationRank, resolveToolResultVideoStateSignature };
