/* SoAI - Plugins feature concurrent manager state [frontend/assets/ts/features/plugins/modals/concurrentmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readBoundedPositiveIntegerTextOrNullValue, readFiniteNumberOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ConcurrentSliderBounds } from '@features/plugins/modals/concurrentmanager/types.ts';

interface ConcurrentModalInitialState {
    normalizedValue: number | null;
    sliderValue: number;
    sliderMax: number;
    inputValue: number | '';
}

interface ConcurrentSliderInputState {
    nextSliderMax: number;
    boundedValue: number;
}

const cloneJsonObject = (source: JsonObject): JsonObject => {
    return Object.fromEntries(Object.entries(source));
};

const normalizeConcurrentValue = (value: number | null, min: number): number | null => {
    const normalized = readFiniteNumberOrNullValue(value);
    if (normalized === null) {
        return null;
    }
    if (normalized < min) {
        return null;
    }
    return normalized;
};

const resolveConcurrentModalInitialState = (value: number | null, bounds: ConcurrentSliderBounds): ConcurrentModalInitialState => {
    const normalizedValue = normalizeConcurrentValue(value, bounds.min);
    const hasValue = normalizedValue !== null;
    const sliderValue = hasValue ? normalizedValue : bounds.min;
    const sliderMax = Math.min(bounds.maxLimit, Math.max(bounds.defaultMax, sliderValue));
    return {
        normalizedValue,
        sliderValue,
        sliderMax,
        inputValue: hasValue ? sliderValue : ''
    };
};

const parseConcurrentInputValue = (rawValue: string, min: number): number | null => {
    const parsed = readBoundedPositiveIntegerTextOrNullValue(rawValue, Number.MAX_SAFE_INTEGER);
    return parsed !== null && parsed >= min ? parsed : null;
};

const resolveSliderInputState = (value: number, currentSliderMax: number, bounds: ConcurrentSliderBounds): ConcurrentSliderInputState => {
    const desiredMax = Math.max(bounds.defaultMax, value);
    const nextSliderMax = Math.min(bounds.maxLimit, Math.max(desiredMax, currentSliderMax));
    const boundedValue = Math.min(value, bounds.maxLimit);
    return { nextSliderMax, boundedValue };
};

const isConcurrentValueModified = (currentValue: number | null, originalValue: number | null): boolean => {
    if (originalValue === null) {
        return currentValue !== null;
    }
    return currentValue !== null && currentValue !== originalValue;
};

const buildConcurrentCoreConfigCache = (currentCache: JsonObject | null, value: number): JsonObject => {
    const cache = currentCache ?? {};
    const modelsCandidate = cache['MODELS'];
    const models = isJsonObject(modelsCandidate) ? cloneJsonObject(modelsCandidate) : {};
    const routingCandidate = models['ROUTING'];
    const routing = isJsonObject(routingCandidate) ? cloneJsonObject(routingCandidate) : {};
    return {
        ...cache,
        MODELS: {
            ...cloneJsonObject(models),
            ROUTING: {
                ...cloneJsonObject(routing),
                MAX_CONCURRENT_PLUGINS: value
            }
        }
    };
};

export { buildConcurrentCoreConfigCache, isConcurrentValueModified, normalizeConcurrentValue, parseConcurrentInputValue, resolveConcurrentModalInitialState, resolveSliderInputState };
