/* SoAI - Prompts picker prompt collection operations [frontend/assets/ts/features/prompts/picker/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { normalizePromptRecord, type PromptRecord } from '@features/prompts/promptRecords.ts';

const comparePromptsPickerPrompts = (left: PromptRecord, right: PromptRecord): number => {
    const modifiedDelta = right.modifiedAtMs - left.modifiedAtMs;
    return modifiedDelta === 0 ? left.id.localeCompare(right.id, 'en') : modifiedDelta;
};

const normalizePromptsPickerPayload = (value: JsonValue): PromptRecord[] => {
    if (!isArray(value)) {
        throw new Error('Prompts picker expected a prompt array payload');
    }
    return value.map((item) => normalizePromptRecord(item)).sort(comparePromptsPickerPrompts);
};

const upsertPromptsPickerPrompt = <T>(prompts: readonly PromptRecord[], record: T): { prompts: PromptRecord[]; prompt: PromptRecord } => {
    const prompt = normalizePromptRecord(record);
    const next = prompts.filter((candidate) => candidate.id !== prompt.id);
    next.push(prompt);
    next.sort(comparePromptsPickerPrompts);
    return { prompts: next, prompt };
};

const filterPromptsPickerPrompts = (prompts: readonly PromptRecord[], query: string): PromptRecord[] => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
        return [...prompts];
    }
    return prompts.filter((prompt) => `${prompt.name} ${prompt.content}`.toLowerCase().includes(normalizedQuery));
};

export { filterPromptsPickerPrompts, normalizePromptsPickerPayload, upsertPromptsPickerPrompt };
