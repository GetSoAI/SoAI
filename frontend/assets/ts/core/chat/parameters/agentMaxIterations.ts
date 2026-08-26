/* SoAI - Shared chat agent max iterations [frontend/assets/ts/core/chat/parameters/agentMaxIterations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters } from '@core/chat/parameters/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const AGENT_MAX_ITERATIONS_PARAMETER_KEY = 'agent_max_iterations';
const DEFAULT_AGENT_MAX_ITERATIONS = 1_000_000;
const MAX_AGENT_MAX_ITERATIONS = 1_000_000_000;

const isValidAgentMaxIterations = (value: JsonValue | undefined): value is number => {
    return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= MAX_AGENT_MAX_ITERATIONS;
};

const normalizeAgentMaxIterationsParameter = (value: JsonValue | undefined): number => {
    return isValidAgentMaxIterations(value) ? value : DEFAULT_AGENT_MAX_ITERATIONS;
};

const readAgentMaxIterationsFromAgentSettings = (agentSettings: JsonValue | undefined): number => {
    if (!isJsonObject(agentSettings)) {
        return DEFAULT_AGENT_MAX_ITERATIONS;
    }
    return normalizeAgentMaxIterationsParameter(agentSettings['max_iterations']);
};

const readAgentMaxIterationsFromModelSettings = (modelSettings: JsonValue | undefined): number => {
    if (!isJsonObject(modelSettings)) {
        return DEFAULT_AGENT_MAX_ITERATIONS;
    }
    return readAgentMaxIterationsFromAgentSettings(modelSettings['agent']);
};

const buildAgentSettingsWithMaxIterations = (parameters: ChatParameters, currentAgentSettings: JsonValue | undefined = undefined): JsonObject => {
    const agentSettings = isJsonObject(currentAgentSettings) ? { ...currentAgentSettings } : {};
    agentSettings['max_iterations'] = normalizeAgentMaxIterationsParameter(parameters.agentMaxIterations);
    return agentSettings;
};

const applyAgentMaxIterationsParameterFromModelSettings = (parameters: ChatParameters, modelSettings: JsonValue | undefined): void => {
    parameters.agentMaxIterations = readAgentMaxIterationsFromModelSettings(modelSettings);
};

export { AGENT_MAX_ITERATIONS_PARAMETER_KEY, DEFAULT_AGENT_MAX_ITERATIONS, MAX_AGENT_MAX_ITERATIONS, applyAgentMaxIterationsParameterFromModelSettings, buildAgentSettingsWithMaxIterations, normalizeAgentMaxIterationsParameter, readAgentMaxIterationsFromAgentSettings, readAgentMaxIterationsFromModelSettings };
