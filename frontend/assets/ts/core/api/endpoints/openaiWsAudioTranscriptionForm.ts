/* SoAI - Shared API OpenAI WebSocket audio transcription form [frontend/assets/ts/core/api/endpoints/openaiWsAudioTranscriptionForm.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

interface RepeatedFormField {
    name: string;
    aliases: readonly string[];
}

const TRANSCRIPTION_STRING_FORM_FIELDS: readonly string[] = Object.freeze(['language', 'prompt', 'chunking_strategy']);
const TRANSCRIPTION_REPEATED_FORM_FIELDS: readonly RepeatedFormField[] = Object.freeze([
    { name: 'include', aliases: Object.freeze(['include', 'include[]']) },
    { name: 'timestamp_granularities', aliases: Object.freeze(['timestamp_granularities', 'timestamp_granularities[]']) },
    { name: 'known_speaker_names', aliases: Object.freeze(['known_speaker_names', 'known_speaker_names[]']) },
    { name: 'known_speaker_references', aliases: Object.freeze(['known_speaker_references', 'known_speaker_references[]']) }
]);

const getFormFieldString = (formData: FormData, field: string): string | null => {
    const entry = formData.get(field);
    if (typeof entry !== 'string') {
        return null;
    }
    const trimmed = entry.trim();
    return trimmed ? trimmed : null;
};

const getFormFieldStrings = (formData: FormData, field: string): string[] => {
    const values: string[] = [];
    for (const entry of formData.getAll(field)) {
        if (typeof entry !== 'string') {
            continue;
        }
        const trimmed = entry.trim();
        if (trimmed) {
            values.push(trimmed);
        }
    }
    return values;
};

const getFormFieldStringsFromAliases = (formData: FormData, aliases: readonly string[]): string[] => {
    const values: string[] = [];
    for (const alias of aliases) {
        values.push(...getFormFieldStrings(formData, alias));
    }
    return values;
};

const parseOptionalFormNumber = (formData: FormData, field: string): number | null => {
    const value = getFormFieldString(formData, field);
    if (value === null) {
        return null;
    }
    const parsed = Number(value);
    if (!isFiniteNumber(parsed)) {
        throw new Error(`Invalid transcription ${field}`);
    }
    return parsed;
};

const readTranscriptionAudioFile = (formData: FormData): File | Blob | null => {
    const entry = formData.get('file');
    if (!entry) {
        return null;
    }
    return typeof entry === 'string' ? null : entry;
};

const readTranscriptionModel = (formData: FormData): string | null => getFormFieldString(formData, 'model');

const readTranscriptionResponseFormat = (formData: FormData): string => getFormFieldString(formData, 'response_format') || 'json';

const validateWebuiTranscriptionFormData = (formData: FormData): void => {
    if (formData.has('stream')) {
        throw new Error('WebUI transcription does not accept stream');
    }
};

const appendTranscriptionStartFormFields = (message: JsonObject, formData: FormData): void => {
    for (const field of TRANSCRIPTION_STRING_FORM_FIELDS) {
        const value = getFormFieldString(formData, field);
        if (value !== null) {
            message[field] = value;
        }
    }
    for (const field of TRANSCRIPTION_REPEATED_FORM_FIELDS) {
        const values = getFormFieldStringsFromAliases(formData, field.aliases);
        if (values.length > 0) {
            message[field.name] = values;
        }
    }
    const temperature = parseOptionalFormNumber(formData, 'temperature');
    if (temperature !== null) {
        message['temperature'] = temperature;
    }
};

export { appendTranscriptionStartFormFields, readTranscriptionAudioFile, readTranscriptionModel, readTranscriptionResponseFormat, validateWebuiTranscriptionFormData };
