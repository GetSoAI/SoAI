/* SoAI - Chat prompts picker prompt collection operations [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { normalizePromptRecord, type PromptRecord } from '@features/prompts/public.ts';

const compareChatPromptsPickerPrompts = (left: PromptRecord, right: PromptRecord): number => {
    const modifiedDelta = right.modifiedAtMs - left.modifiedAtMs;
    return modifiedDelta === 0 ? left.id.localeCompare(right.id, 'en') : modifiedDelta;
};

const normalizeChatPromptsPickerPayload = (value: JsonValue): PromptRecord[] => {
    if (!isArray(value)) {
        throw new Error('Chat prompts picker expected a prompt array payload');
    }
    return value.map((item) => normalizePromptRecord(item)).sort(compareChatPromptsPickerPrompts);
};

const normalizeChatPromptsPickerPrompt = <T>(record: T): PromptRecord => {
    return normalizePromptRecord(record);
};

const upsertChatPromptsPickerPrompt = <T>(prompts: readonly PromptRecord[], record: T): { prompts: PromptRecord[]; prompt: PromptRecord } => {
    const prompt = normalizeChatPromptsPickerPrompt(record);
    const next = prompts.filter((candidate) => candidate.id !== prompt.id);
    next.push(prompt);
    next.sort(compareChatPromptsPickerPrompts);
    return { prompts: next, prompt };
};

const filterChatPromptsPickerPrompts = (prompts: readonly PromptRecord[], query: string): PromptRecord[] => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
        return [...prompts];
    }
    return prompts.filter((prompt) => `${prompt.name} ${prompt.content}`.toLowerCase().includes(normalizedQuery));
};

export { filterChatPromptsPickerPrompts, normalizeChatPromptsPickerPayload, normalizeChatPromptsPickerPrompt, upsertChatPromptsPickerPrompt };
