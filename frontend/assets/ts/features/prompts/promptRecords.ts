/* SoAI - Shared prompt record normalization [frontend/assets/ts/features/prompts/promptRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { normalizeColor } from '@core/ui/colorToolkitBase.ts';
import { isEpochMsValue, parseEpochMsOrNull } from '@core/time/epochMs.ts';
import { isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PromptRecord {
    id: string;
    name: string;
    content: string;
    color: string | null;
    createdAtMs: number;
    modifiedAtMs: number;
}

const normalizePromptRecordId = (value: JsonValue | undefined): string => {
    if (isString(value) && value.trim()) {
        return value.trim();
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return String(value);
    }
    throw new Error('Prompt record is missing id');
};

const normalizePromptRecordText = (value: JsonValue | undefined, fieldName: string): string => {
    if (isString(value)) {
        return value;
    }
    if (value === null || value === undefined) {
        return '';
    }
    throw new Error(`Prompt record ${fieldName} must be a string`);
};

const normalizePromptRecordTimestamp = (value: JsonValue | undefined, fieldName: string): number => {
    const timestamp = parseEpochMsOrNull(value);
    if (timestamp !== null) {
        return timestamp;
    }
    throw new Error(`Prompt record is missing ${fieldName}`);
};

const normalizePromptRecordColor = (value: JsonValue | undefined): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (!isString(value)) {
        throw new Error('Prompt record color must be a string or null');
    }
    return normalizeColor(value);
};

const isPromptRecord = <T>(value: T): value is T & PromptRecord => {
    if (!isJsonObject(value)) {
        return false;
    }
    if (!isString(value['id']) || !isString(value['name']) || !isString(value['content'])) {
        return false;
    }
    const color = value['color'];
    if (color !== null && !isString(color)) {
        return false;
    }
    return isEpochMsValue(value['createdAtMs']) && isEpochMsValue(value['modifiedAtMs']);
};

const buildPromptDownloadText = (prompt: PromptRecord): string => {
    const name = (prompt.name || i18n.t('prompts.unnamedPrompt')).trim();
    const created = new Date(prompt.createdAtMs).toISOString();
    const updated = new Date(prompt.modifiedAtMs).toISOString();
    return ['SoAI prompt', `Created: ${created}`, `Updated: ${updated}`, '', `### ${name}`, '', prompt.content].join('\n');
};

const normalizePromptRecord = <T>(value: T): PromptRecord => {
    if (!isJsonObject(value)) {
        throw new Error('Prompt record must be an object');
    }
    const id = normalizePromptRecordId(value['id']);
    const name = normalizePromptRecordText(value['name'], 'name').trim() || i18n.t('prompts.untitled');
    const content = normalizePromptRecordText(value['content'], 'content');
    const createdSource = value['createdAtMs'];
    const modifiedSource = value['modifiedAtMs'];
    const createdAtMs = normalizePromptRecordTimestamp(createdSource, 'created timestamp');
    const modifiedAtMs = normalizePromptRecordTimestamp(modifiedSource, 'modified timestamp');
    return {
        id,
        name,
        content,
        color: normalizePromptRecordColor(value['color']),
        createdAtMs: createdAtMs,
        modifiedAtMs: modifiedAtMs
    };
};

export { buildPromptDownloadText, isPromptRecord, normalizePromptRecord };
export type { PromptRecord };
