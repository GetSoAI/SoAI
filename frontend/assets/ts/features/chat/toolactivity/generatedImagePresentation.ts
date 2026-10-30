/* SoAI - Pure generated image widget presentation and visibility signatures [frontend/assets/ts/features/chat/toolactivity/generatedImagePresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractErrorCode } from '@core/errors/coerce.ts';
import { getLocalizationSnapshot } from '@core/localization/public.ts';
import { resolveSkillErrorMessage } from '@core/skills/errorPresentation.ts';
import { resolvePayloadRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import { isPositiveInteger, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import type { InlineToolActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveToolImageDescriptor, resolveOmittedToolImageDescriptor, type ToolImagePayload } from '@features/chat/toolactivity/toolImagePayload.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { resolveToolOutputTruncation } from '@features/chat/toolactivity/toolOutputPresentation.ts';
import { resolveToolResultMediaStateSignature } from '@features/chat/toolactivity/toolMediaSignatures.ts';

type ImagePresentationInput = Pick<ToolActivityItem, 'callId' | 'toolName' | 'status' | 'inputArguments' | 'result' | 'error' | 'startedAtMs' | 'durationMs'>;
type ActivityWidgetVisibility = 'active' | 'settled';
type GeneratedImagePresentation = Readonly<{ state: ToolActivityItem['status'] | 'unavailable'; prompt: string; geometry: Readonly<{ width: number; height: number }> | null; payload: ToolImagePayload | null; error: string; signature: string }>;

const resolveImageGeometry = (record: JsonValue | undefined): Readonly<{ width: number; height: number }> | null => {
    if (!isJsonObject(record)) return null;
    const width = record['width'];
    const height = record['height'];
    return isPositiveInteger(width) && isPositiveInteger(height) && Number.isSafeInteger(width) && Number.isSafeInteger(height) ? { width, height } : null;
};

const resolveGeneratedImagePresentation = (input: ImagePresentationInput): GeneratedImagePresentation | null => {
    if (normalizeToolLeafName(input.toolName) !== 'generate_image') return null;
    const descriptor = resolveToolImageDescriptor(input.result, { toolLeafName: 'generate_image' });
    const omitted = resolveOmittedToolImageDescriptor(input.result, { toolLeafName: 'generate_image' });
    const argumentsRecord = isJsonObject(input.inputArguments) ? input.inputArguments : null;
    const prompt = isString(argumentsRecord?.['prompt']) ? argumentsRecord['prompt'] : '';
    const geometry = (input.status === 'completed' ? resolveImageGeometry(descriptor?.record ?? omitted?.record ?? input.result) : null) ?? resolveImageGeometry(input.inputArguments);
    const payload = input.status === 'completed' ? (descriptor?.payload ?? null) : null;
    const state = input.status === 'completed' ? (payload === null ? 'unavailable' : 'completed') : input.status;
    const resultRecord = resolvePayloadRecord(input.result);
    const error = input.status === 'error' ? (resolveSkillErrorMessage(extractErrorCode(resultRecord)) ?? resolveSkillErrorMessage(extractErrorCode(resultRecord?.['data'])) ?? input.error?.trim() ?? '') : '';
    const localization = getLocalizationSnapshot();
    const signature = JSON.stringify([localization.preferences.language, localization.locale, localization.dateOrder, localization.hour12, input.callId, state, prompt, geometry, error, input.startedAtMs ?? null, input.status === 'running' ? null : (input.durationMs ?? null), resolveToolOutputTruncation(input.result), resolveToolResultMediaStateSignature(input.result, { toolLeafName: 'generate_image' })]);
    return { state, prompt, geometry, payload, error, signature };
};

const resolveActivityWidgetSegments = (segments: readonly MessageSegment[], visibility: ActivityWidgetVisibility): readonly MessageSegment[] => (visibility === 'settled' ? segments : segments.filter((segment) => segment.type === 'inline_tool_activity' && normalizeToolLeafName(segment.toolName) === 'generate_image'));

const resolveActiveImageWidgetsSignature = (segments: readonly MessageSegment[]): string => JSON.stringify(segments.filter((segment): segment is InlineToolActivitySegment => segment.type === 'inline_tool_activity' && normalizeToolLeafName(segment.toolName) === 'generate_image').map((segment) => resolveGeneratedImagePresentation(segment)?.signature));

export { resolveActiveImageWidgetsSignature, resolveActivityWidgetSegments, resolveGeneratedImagePresentation };
export type { ActivityWidgetVisibility };
