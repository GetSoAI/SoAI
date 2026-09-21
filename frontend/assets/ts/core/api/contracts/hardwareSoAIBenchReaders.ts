/* SoAI - Shared frontend API contract boundary hardware SoAI bench readers [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

interface SoAIBenchClassification {
    scoreClassification: 'current' | 'legacy' | 'unsupported_legacy';
    legacyScore: boolean;
    publicationEligible: boolean;
}

const readSoAIBenchClassification = (record: JsonObject, label: string): SoAIBenchClassification => {
    const hasClassification = ['score_classification', 'legacy_score', 'publication_eligible'].some((field) => hasOwn(record, field));
    if (!hasClassification) {
        const score = record['score'];
        const scoreVersion = record['score_version'] ?? (isJsonObject(score) ? score['score_version'] : undefined);
        if (scoreVersion === 'soaibench-v2') throw new TypeError(`${label}.score_classification is required for soaibench-v2`);
        return { scoreClassification: scoreVersion === 'soaibench-v1' ? 'legacy' : 'unsupported_legacy', legacyScore: true, publicationEligible: false };
    }
    const scoreClassification = readRequiredTrimmedStringValue(record['score_classification'], `${label}.score_classification`);
    const legacyScore = readRequiredBooleanValue(record['legacy_score'], `${label}.legacy_score`);
    const publicationEligible = readRequiredBooleanValue(record['publication_eligible'], `${label}.publication_eligible`);
    if (scoreClassification !== 'current' && scoreClassification !== 'legacy' && scoreClassification !== 'unsupported_legacy') throw new TypeError(`${label}.score_classification is invalid`);
    if (legacyScore !== (scoreClassification !== 'current') || (publicationEligible && scoreClassification !== 'current')) throw new TypeError(`${label} classification is inconsistent`);
    return { scoreClassification, legacyScore, publicationEligible };
};

const readSoAIBenchOptionalNumber = (record: JsonObject, key: string, label: string): number | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isFiniteNumber(value)) return value;
    throw new TypeError(`${label}.${key} must be a finite number or null`);
};

const readSoAIBenchOptionalString = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isString(value)) return value;
    throw new TypeError(`${label}.${key} must be a string or null`);
};

const readSoAIBenchOptionalBoolean = (record: JsonObject, key: string, label: string): boolean | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isBoolean(value)) return value;
    throw new TypeError(`${label}.${key} must be a boolean or null`);
};

const readSoAIBenchOptionalStringList = (record: JsonObject, key: string, label: string): string[] | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null) return null;
    if (!Array.isArray(value) || !value.every(isString)) throw new TypeError(`${label}.${key} must be a string array or null`);
    return value;
};

export { readSoAIBenchClassification, readSoAIBenchOptionalBoolean, readSoAIBenchOptionalNumber, readSoAIBenchOptionalString, readSoAIBenchOptionalStringList };
export type { SoAIBenchClassification };
