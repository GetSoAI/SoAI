/* SoAI - Shared frontend log normalization [frontend/assets/ts/core/logNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { getLogValidation } from '@core/logvalidation/public.ts';
import type { JsonValue, JsonObject } from '@core/types/jsonValues.ts';
import { getTypeOf, isArray, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface LogEntry extends JsonObject {
    timestamp: string;
    component: string;
    level: string;
    message: string;
    text: string;
}

interface RawLogEntry {
    timestamp?: JsonValue | null | undefined;
    component?: JsonValue | null | undefined;
    level?: JsonValue | null | undefined;
    message?: JsonValue | null | undefined;
    text?: JsonValue | null | undefined;
}

class LogNormalizer {
    normalizeLogEntry(entry: JsonValue | null | undefined): LogEntry {
        if (!isObject(entry) || isArray(entry)) {
            throw new Error(`Cannot normalize log entry: expected object, got ${getTypeOf(entry)}`);
        }

        const rawEntry = entry;
        const timestampValue = rawEntry['timestamp'];
        const componentValue = rawEntry['component'];
        const levelValue = rawEntry['level'];
        const messageValue = rawEntry['message'];
        const textValue = rawEntry['text'];

        if (!isString(timestampValue)) {
            throw new Error(`Invalid log entry: timestamp must be string, got ${getTypeOf(timestampValue)}`);
        }

        if (!isString(componentValue) || componentValue.trim().length === 0) {
            throw new Error(`Invalid log entry: component must be non-empty string, got ${getTypeOf(componentValue)}`);
        }

        if (!isString(levelValue) || !getLogValidation().isValidLogLevel(levelValue)) {
            throw new Error(`Invalid log entry: level must be valid log level, got ${String(levelValue)}`);
        }

        const message = isString(messageValue) ? messageValue : null;
        const text = isString(textValue) ? textValue : null;
        const resolvedMessage = message && message.trim().length > 0 ? message : text && text.trim().length > 0 ? text : null;
        const resolvedText = text && text.trim().length > 0 ? text : message && message.trim().length > 0 ? message : null;
        if (!resolvedMessage) {
            throw new Error(`Invalid log entry: requires message or text, got ${getTypeOf(messageValue)} / ${getTypeOf(textValue)}`);
        }
        if (!resolvedText) {
            throw new Error(`Invalid log entry: requires text or message, got ${getTypeOf(textValue)} / ${getTypeOf(messageValue)}`);
        }

        const normalized: LogEntry = {
            timestamp: timestampValue,
            component: componentValue.trim(),
            level: levelValue.toUpperCase(),
            message: resolvedMessage,
            text: resolvedText
        };

        const validationInput: JsonValue = {
            timestamp: normalized.timestamp,
            component: normalized.component,
            level: normalized.level,
            message: normalized.message,
            text: normalized.text
        };
        const validation = getLogValidation().validateLogEntry(validationInput);
        if (!validation.valid) {
            throw new Error(`Log validation failed: ${validation.errors.join(', ')}`);
        }

        return normalized;
    }

    normalizeBatch(entries: JsonValue | null | undefined): LogEntry[] {
        if (!isArray(entries)) {
            throw new Error(`Cannot normalize batch: expected array, got ${getTypeOf(entries)}`);
        }

        const normalized: LogEntry[] = [];

        for (let index = 0; index < entries.length; index++) {
            try {
                normalized.push(this.normalizeLogEntry(entries[index]));
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.error('LogNormalization', `Failed to normalize entry ${index}`, runtimeError);
                const message = runtimeError.message;
                throw new Error(`Batch normalization failed at entry ${index}: ${message}`);
            }
        }

        return normalized;
    }
}

let logNormalizationInstance: LogNormalizer | null = null;

const getLogNormalization = (): LogNormalizer => {
    if (!logNormalizationInstance) {
        logNormalizationInstance = new LogNormalizer();
    }
    return logNormalizationInstance;
};

export { LogNormalizer, getLogNormalization };

export type { LogEntry, RawLogEntry };
