/* SoAI - Tool media payload state signatures [frontend/assets/ts/features/chat/toolactivity/toolMediaSignatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasToolResultInlineImageBase64, hasToolResultOmittedInlineImageBase64, resolveToolResultImageHydrationRank, resolveToolResultImageStateSignature, type ToolImageDescriptorOptions } from '@features/chat/toolactivity/toolImageSignatures.ts';
import { hasToolResultInlineVideoBase64, hasToolResultOmittedInlineVideoBase64, resolveToolResultVideoHydrationRank, resolveToolResultVideoStateSignature } from '@features/chat/toolactivity/toolVideoSignatures.ts';

const hasToolResultInlineMediaBase64 = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): boolean => hasToolResultInlineImageBase64(value, options) || hasToolResultInlineVideoBase64(value);

const hasToolResultOmittedInlineMediaBase64 = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): boolean => hasToolResultOmittedInlineImageBase64(value, options) || hasToolResultOmittedInlineVideoBase64(value);

const resolveToolResultMediaHydrationRank = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): number => Math.max(resolveToolResultImageHydrationRank(value, options), resolveToolResultVideoHydrationRank(value));

const resolveToolResultMediaStateSignature = (value: JsonValue | undefined, options: ToolImageDescriptorOptions = {}): string => {
    return [resolveToolResultImageStateSignature(value, options), resolveToolResultVideoStateSignature(value)].join('|');
};

export { hasToolResultInlineMediaBase64, hasToolResultOmittedInlineMediaBase64, resolveToolResultMediaHydrationRank, resolveToolResultMediaStateSignature };
