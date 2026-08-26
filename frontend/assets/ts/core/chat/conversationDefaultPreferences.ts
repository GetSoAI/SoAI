/* SoAI - Sparse V1 conversation-default preference codec [frontend/assets/ts/core/chat/conversationDefaultPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDefaultChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_PARAMETER_WIRE_KEYS, CHAT_WIRE_TO_PARAMETER_KEYS, STORED_CHAT_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { getParameterMeta } from '@core/chat/parameters/chatParameterMeta.ts';
import { isReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { isChatServiceTier } from '@core/chat/parameters/serviceTier.ts';
import { isUnicodeScalarText, trimPythonWhitespace } from '@core/primitives/text.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const ROOT_KEYS = new Set(['model', 'parameters', 'agent', 'mcp']);
const AGENT_KEYS = new Set(['max_iterations']);
const MCP_KEYS = new Set(['tools_enabled', 'tool_approval_required']);
const BOOLEAN_PARAMETERS = new Set(['logprobs', 'reasoningEffortSendEnabled', 'maxCompletionTokensSendEnabled', 'topPSendEnabled', 'frequencyPenaltySendEnabled', 'presencePenaltySendEnabled', 'stopSendEnabled', 'logprobsSendEnabled']);
const NULLABLE_NUMBERS = new Set(['contextWindowTokens', 'maxCompletionTokens', 'topLogprobs']);
const PARAMETER_KEYS = new Set(STORED_CHAT_PARAMETER_KEYS.map((key) => CHAT_PARAMETER_WIRE_KEYS[key] ?? key));

const exactKeys = (record: JsonObject, allowed: ReadonlySet<string>): boolean => Object.keys(record).every((key) => allowed.has(key));
const scalarString = (value: JsonValue): value is string => typeof value === 'string' && trimPythonWhitespace(value).length > 0 && trimPythonWhitespace(value) === value && isUnicodeScalarText(value);

const validParameter = (wireKey: string, value: JsonValue): boolean => {
    const key = CHAT_WIRE_TO_PARAMETER_KEYS[wireKey] ?? wireKey;
    if (BOOLEAN_PARAMETERS.has(key)) return typeof value === 'boolean';
    if (key === 'stop') return Array.isArray(value) && value.length <= 50 && value.every((entry) => typeof entry === 'string' && isUnicodeScalarText(entry));
    if (key === 'reasoningEffort') return value === null || (typeof value === 'string' && isReasoningEffortLevel(value));
    if (key === 'serviceTier') return value === null || (typeof value === 'string' && isChatServiceTier(value));
    if (NULLABLE_NUMBERS.has(key) && value === null) return true;
    if (typeof value !== 'number' || !Number.isFinite(value)) return false;
    const meta = getParameterMeta(key);
    if (meta?.min !== undefined && value < meta.min) return false;
    if (meta?.max !== undefined && value > meta.max) return false;
    if (key === 'contextWindowTokens') return Number.isSafeInteger(value) && value > 0;
    if (key === 'maxCompletionTokens') return Number.isSafeInteger(value) && value >= 0 && value <= 4_194_304;
    if (key === 'topLogprobs') return Number.isSafeInteger(value) && value >= 0;
    if (key === 'completionCount') return Number.isSafeInteger(value) && value >= 1;
    return true;
};

const decodeConversationDefaultDelta = (value: JsonValue): JsonObject | null => {
    if (!isJsonObject(value) || !exactKeys(value, ROOT_KEYS)) return null;
    const model = value['model'];
    if (model !== undefined && model !== null && !scalarString(model)) return null;
    const parameters = value['parameters'];
    if (parameters !== undefined) {
        if (!isJsonObject(parameters) || Object.keys(parameters).length === 0 || !exactKeys(parameters, PARAMETER_KEYS)) return null;
        if (Object.entries(parameters).some(([key, entry]) => !validParameter(key, entry))) return null;
    }
    const agent = value['agent'];
    if (agent !== undefined) {
        if (!isJsonObject(agent) || !exactKeys(agent, AGENT_KEYS) || Object.keys(agent).length === 0) return null;
        const maximum = agent['max_iterations'];
        if (typeof maximum !== 'number' || !Number.isSafeInteger(maximum) || maximum < 1 || maximum > 1_000_000_000) return null;
    }
    const mcp = value['mcp'];
    if (mcp !== undefined) {
        if (!isJsonObject(mcp) || !exactKeys(mcp, MCP_KEYS) || Object.keys(mcp).length === 0 || Object.values(mcp).some((entry) => typeof entry !== 'boolean')) return null;
    }
    return structuredClone(value);
};

const conversationDefaultTemplate = (): JsonObject => {
    const defaults = getDefaultChatParameters();
    const parameters: JsonObject = {};
    for (const key of STORED_CHAT_PARAMETER_KEYS) parameters[CHAT_PARAMETER_WIRE_KEYS[key] ?? key] = defaults[key] ?? null;
    return { model: null, parameters, agent: { 'max_iterations': defaults.agentMaxIterations ?? 1_000_000 }, mcp: { 'tools_enabled': defaults.toolsEnabled === true, 'tool_approval_required': defaults.toolApprovalRequired === true } };
};

const mergeConversationDefaultDelta = (base: JsonObject, delta: JsonObject): JsonObject => {
    const merged = structuredClone(base);
    for (const [key, value] of Object.entries(delta)) {
        const current = merged[key];
        merged[key] = isJsonObject(current) && isJsonObject(value) ? mergeConversationDefaultDelta(current, value) : structuredClone(value);
    }
    return merged;
};

export { conversationDefaultTemplate, decodeConversationDefaultDelta, mergeConversationDefaultDelta };
