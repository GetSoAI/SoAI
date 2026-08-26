/* SoAI - Tool image payload state signatures [frontend/assets/ts/features/chat/toolactivity/toolImageSignatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { collectToolImageStateSignatures, resolveOmittedToolImageDescriptor, resolveToolImageDescriptor, resolveToolImageHydrationRank, type ToolImageDescriptorOptions } from '@features/chat/toolactivity/toolImagePayload.ts';

interface ToolImagePayloadCounts {
    inlineCount: number;
    inlineChars: number;
    omittedCount: number;
    omittedChars: number;
    signatures: string[];
}

const emptyCounts = (): ToolImagePayloadCounts => ({
    inlineCount: 0,
    inlineChars: 0,
    omittedCount: 0,
    omittedChars: 0,
    signatures: []
});

const countToolImagePayloadState = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): ToolImagePayloadCounts => {
    const counts = emptyCounts();
    const inline = resolveToolImageDescriptor(value, options);
    if (inline !== null) {
        counts.inlineCount += 1;
        counts.inlineChars += inline.payload.imageBase64.length;
    }
    const omitted = resolveOmittedToolImageDescriptor(value, options);
    if (omitted !== null) {
        counts.omittedCount += 1;
        counts.omittedChars += omitted.totalChars ?? 0;
    }
    counts.signatures.push(...collectToolImageStateSignatures(value, [], options));
    return counts;
};

const hasToolResultInlineImageBase64 = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): boolean => resolveToolImageDescriptor(value, options) !== null;

const hasToolResultOmittedInlineImageBase64 = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): boolean => resolveOmittedToolImageDescriptor(value, options) !== null;

const resolveToolResultImageHydrationRank = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): number => resolveToolImageHydrationRank(value, options);

const resolveToolResultImageStateSignature = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): string => {
    const counts = countToolImagePayloadState(value, options);
    const sortedSignatures = counts.signatures.sort((left, right) => left.localeCompare(right, 'en'));
    return [`inline:${String(counts.inlineCount)}:${String(counts.inlineChars)}`, `omitted:${String(counts.omittedCount)}:${String(counts.omittedChars)}`, sortedSignatures.join('|')].join('|');
};

export { hasToolResultInlineImageBase64, hasToolResultOmittedInlineImageBase64, resolveToolResultImageHydrationRank, resolveToolResultImageStateSignature };
export type { ToolImageDescriptorOptions };
