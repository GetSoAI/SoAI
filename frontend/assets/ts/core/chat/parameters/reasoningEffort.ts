/* SoAI - Canonical reasoning effort capability domain [frontend/assets/ts/core/chat/parameters/reasoningEffort.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

enum ReasoningEffortLevel {
    None = 'none',
    Minimal = 'minimal',
    Low = 'low',
    Medium = 'medium',
    High = 'high',
    ExtraHigh = 'xhigh',
    Maximum = 'max'
}

const REASONING_EFFORT_LEVELS: readonly ReasoningEffortLevel[] = Object.freeze(Object.values(ReasoningEffortLevel));
const REASONING_EFFORT_LEVEL_SET: ReadonlySet<string> = new Set(REASONING_EFFORT_LEVELS);

const isReasoningEffortLevel = (value: string): value is ReasoningEffortLevel => REASONING_EFFORT_LEVEL_SET.has(value);

const readReasoningEffortCandidate = (value: JsonValue): string => {
    if (isString(value)) return toTrimmedString(value).toLowerCase();
    if (isJsonObject(value)) return toTrimmedString(value['effort']).toLowerCase();
    return '';
};

const parseSupportedReasoningLevels = (capabilities: JsonObject | null): readonly ReasoningEffortLevel[] | null => {
    if (!capabilities || !Object.hasOwn(capabilities, 'supported_reasoning_levels')) return null;
    const rawLevels = capabilities['supported_reasoning_levels'];
    if (!isArray(rawLevels)) return null;
    const supported = new Set<string>();
    for (const rawLevel of rawLevels) {
        const normalized = readReasoningEffortCandidate(rawLevel);
        if (isReasoningEffortLevel(normalized)) supported.add(normalized);
    }
    return Object.freeze(REASONING_EFFORT_LEVELS.filter((level) => supported.has(level)));
};

const intersectSupportedReasoningLevels = (supportedLevelSets: readonly (readonly ReasoningEffortLevel[] | null)[]): readonly ReasoningEffortLevel[] | null => {
    const explicitSets = supportedLevelSets.filter((levels): levels is readonly ReasoningEffortLevel[] => levels !== null);
    if (explicitSets.length === 0) return null;
    return Object.freeze(REASONING_EFFORT_LEVELS.filter((level) => explicitSets.every((levels) => levels.includes(level))));
};

const isReasoningEffortSupported = (value: string | null | undefined, supportedLevels: readonly ReasoningEffortLevel[] | null): boolean => {
    if (value === null || value === undefined || value === '') return true;
    if (supportedLevels === null) return isReasoningEffortLevel(value);
    return isReasoningEffortLevel(value) && supportedLevels.includes(value);
};

export { REASONING_EFFORT_LEVELS, ReasoningEffortLevel, intersectSupportedReasoningLevels, isReasoningEffortLevel, isReasoningEffortSupported, parseSupportedReasoningLevels };
