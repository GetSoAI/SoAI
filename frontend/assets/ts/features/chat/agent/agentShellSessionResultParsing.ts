/* SoAI - Chat feature agent shell session result parsing [frontend/assets/ts/features/chat/agent/agentShellSessionResultParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

type ParsedShellSessionToolResult = {
    sessionId: number;
    output: string;
    exitCode: number | null;
};

const parseShellSessionId = (value: JsonValue | null | undefined): number | null => readNonNegativeIntegerOrNullValue(value);

const parseShellExitCode = (value: JsonValue | null | undefined): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readNonNegativeIntegerOrNullValue(value);
};

const parseShellOutput = (value: JsonValue | null | undefined): string | null => {
    if (!isString(value)) {
        return null;
    }
    return value;
};

const tryParseShellSessionToolResultRecord = (record: Record<string, JsonValue | null | undefined>): ParsedShellSessionToolResult | null => {
    const sessionId = parseShellSessionId(record['session_id']);
    if (sessionId === null) {
        return null;
    }
    const output = parseShellOutput(record['output']);
    if (output === null) {
        return null;
    }
    const exitCode = parseShellExitCode(record['exit_code']);
    return {
        sessionId: sessionId,
        output,
        exitCode: exitCode
    };
};

const tryParseShellSessionToolResult = (value: JsonValue | null | undefined): ParsedShellSessionToolResult | null => {
    if (isString(value)) {
        const trimmed = value.trim();
        if (!trimmed) {
            return null;
        }
        if (!trimmed.startsWith('{')) {
            return null;
        }
        try {
            const parsed = parseRequiredJsonText(trimmed);
            return tryParseShellSessionToolResult(parsed);
        } catch (error) {
            errorHandler.warn('AgentShellSessionResultParsing', 'Failed to parse shell session tool result JSON', ensureError(error));
            return null;
        }
    }
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    return tryParseShellSessionToolResultRecord(value);
};

const isShellSessionInProgressToolResult = (value: JsonValue | null | undefined): boolean => {
    const parsed = tryParseShellSessionToolResult(value);
    return parsed !== null && parsed.exitCode === null;
};

const serializeShellSessionToolResult = (parsed: ParsedShellSessionToolResult): Record<string, JsonValue | null> => {
    return {
        sessionId: parsed.sessionId,
        output: parsed.output,
        exitCode: parsed.exitCode
    };
};

export { isShellSessionInProgressToolResult, serializeShellSessionToolResult, tryParseShellSessionToolResult };
export type { ParsedShellSessionToolResult };
