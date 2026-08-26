/* SoAI - Shared state status normalization [frontend/assets/ts/core/state/statusNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedStringOrNull, toUpperCase } from '@core/normalize.ts';
import { DEFAULT_STATUS_ALLOWED_COLORS, DEFAULT_STATUS_DEFINITIONS, type StatusDefinition, type StatusDefinitions } from '@core/state/constants.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

const normalizeStatusKey = (value: JsonValue | null | undefined): string | null => {
    const trimmed = toTrimmedStringOrNull(value);
    return trimmed ? toUpperCase(trimmed) : null;
};

const isStatusColor = (value: JsonValue | null | undefined): value is StatusDefinition['color'] => {
    switch (value) {
        case 'grey':
        case 'orange':
        case 'green':
        case 'blue':
        case 'red':
        case 'darkgreen':
        case 'persistentgreen':
            return true;
        default:
            return false;
    }
};

const resolveDefinitionColor = (key: string, definition: PayloadEntry, defaultDefinition: StatusDefinition | null): StatusDefinition['color'] => {
    const candidate = isString(definition.color) ? definition.color.trim() : '';
    if (candidate) {
        if (!isStatusColor(candidate)) {
            throw new Error(`Status definition "${key}" provided unsupported color "${candidate}"`);
        }
        return candidate;
    }
    if (defaultDefinition) {
        return defaultDefinition.color;
    }
    throw new Error(`Status definition "${key}" must provide a supported color`);
};

const normalizeDefinitionEntry = (key: string, definition: PayloadEntry = {}): StatusDefinition => {
    const defaultDefinition = DEFAULT_STATUS_DEFINITIONS[key] ?? null;
    const color = resolveDefinitionColor(key, definition, defaultDefinition);
    const description = isString(definition.description) ? definition.description.trim() : '';
    if (!defaultDefinition && !description) {
        throw new Error(`Status definition "${key}" must provide description`);
    }
    const normalized: StatusDefinition = defaultDefinition ? { color, description: '' } : { color, description };
    const groupCandidate = isString(definition.group) ? definition.group.trim() : '';
    if (groupCandidate) {
        normalized.group = groupCandidate;
    }
    return normalized;
};

interface PayloadEntry {
    name?: JsonValue | null | undefined;
    color?: JsonValue | null | undefined;
    description?: JsonValue | null | undefined;
    group?: JsonValue | null | undefined;
}

const deriveDefinitions = (payload: Record<string, PayloadEntry> = {}): StatusDefinitions => {
    const merged: StatusDefinitions = { ...DEFAULT_STATUS_DEFINITIONS };
    Object.entries(payload).forEach(([rawKey, rawValue]) => {
        const candidateKey = normalizeStatusKey(isObject(rawValue) && rawValue['name'] ? rawValue['name'] : rawKey);
        if (!candidateKey) {
            return;
        }
        merged[candidateKey] = normalizeDefinitionEntry(candidateKey, rawValue);
    });
    return merged;
};

const deriveAllowedColors = (candidateColors: JsonValue | null | undefined, definitions: StatusDefinitions): string[] => {
    const colors = isArray(candidateColors) ? candidateColors.map((color) => (isString(color) ? color.trim() : '')).filter(Boolean) : [];
    const definitionColors = Object.values(definitions)
        .map((entry) => entry.color)
        .filter((color) => isString(color) && color.trim());
    return Array.from(new Set([...colors, ...definitionColors, ...DEFAULT_STATUS_ALLOWED_COLORS]));
};

const deriveStatusSet = (candidateStatuses: JsonValue | null | undefined, definitions: StatusDefinitions): string[] => {
    const safeDefinitions = isObject(definitions) ? definitions : {};
    const source = isArray(candidateStatuses) ? candidateStatuses : [];
    const normalized = source.map((status) => normalizeStatusKey(status)).filter((status, index, list): status is string => status !== null && safeDefinitions[status] !== undefined && list.indexOf(status) === index);
    return normalized;
};

export { deriveAllowedColors, deriveDefinitions, deriveStatusSet, normalizeStatusKey };
