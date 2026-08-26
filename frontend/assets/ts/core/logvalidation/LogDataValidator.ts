/* SoAI - Frontend log validation ownership [frontend/assets/ts/core/logvalidation/LogDataValidator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedUpper } from '@core/normalize.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { getTypeOf, isArray, isFunction, isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { EntriesValidationResult, LogEntry, LogLineLimitResult, ReplayLimitResult, StrictValidationResult, TextZoomResult, ValidationResult } from '@core/logvalidation/types.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const VALID_LOG_LEVELS: readonly string[] = Object.freeze(['TRACE', 'DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL']);
const VALID_LOG_LEVEL_SET = new Set(VALID_LOG_LEVELS);

const VALID_LOG_LINE_LIMITS: readonly number[] = Object.freeze([100, 250, 500, 1000, 2000, 5000]);
const TEXT_ZOOM_MIN = 0.5;
const TEXT_ZOOM_MAX = 2;
const MAX_REPLAY_LIMIT = 5000;

class LogDataValidator {
    validateLogEntry(entry: JsonValue | LogEntry | null | undefined): ValidationResult {
        const errors: string[] = [];

        if (!isObject(entry)) {
            errors.push('Log entry must be a valid object');
            return { valid: false, errors, entry: null };
        }

        const logEntry = entry;
        const timestampValue = logEntry['timestamp'];
        const componentValue = logEntry['component'];
        const levelValue = logEntry['level'];
        const messageValue = logEntry['message'];
        const textValue = logEntry['text'];

        const timestamp = isString(timestampValue) && timestampValue.trim() ? timestampValue : null;
        const component = isString(componentValue) && componentValue.trim() ? componentValue.trim() : null;
        const rawMessage = isString(messageValue) && messageValue.trim() ? messageValue : null;
        const rawText = isString(textValue) && textValue.trim() ? textValue : null;
        const message = rawMessage ?? rawText;
        const text = rawText ?? rawMessage;

        if (timestamp === null) {
            errors.push('Timestamp must be a non-empty string');
        } else if (!this.#isValidTimestamp(timestamp)) {
            errors.push('Timestamp must be ISO-8601 formatted string');
        }

        if (component === null) {
            errors.push('Component must be a non-empty string');
        }

        if (!isString(levelValue) || !this.isValidLogLevel(levelValue)) {
            errors.push(`Invalid log level: ${String(levelValue ?? 'undefined')}. Must be one of: ${VALID_LOG_LEVELS.join(', ')}`);
        }

        if (message === null) {
            errors.push('Message must be a non-empty string');
        }

        if (text === null) {
            errors.push('Text must be a non-empty string');
        }

        if (errors.length > 0) {
            return { valid: false, errors, entry: null };
        }
        if (timestamp === null || component === null || message === null || text === null) {
            throw new Error('Log validation invariant failed');
        }

        const metadataValue = logEntry['metadata'];
        const contextValue = logEntry['context'];
        const metadataHostname = isObject(metadataValue) ? metadataValue['hostname'] : null;
        const metadataPid = isObject(metadataValue) ? metadataValue['pid'] : null;
        const normalizedMetadata: LogEntry['metadata'] | undefined = isObject(metadataValue)
            ? {
                  ...(isString(metadataHostname) ? { hostname: metadataHostname } : {}),
                  ...(isNumber(metadataPid) ? { pid: metadataPid } : {})
              }
            : undefined;
        const normalizedContext: LogEntry['context'] | undefined = isObject(contextValue)
            ? Object.entries(contextValue).reduce<NonNullable<LogEntry['context']>>((entries, [key, value]) => {
                  if (isJsonValue(value) || value === undefined) {
                      entries[key] = value;
                  }
                  return entries;
              }, {})
            : undefined;
        const normalizedEntry: LogEntry = {
            timestamp,
            component,
            level: toTrimmedUpper(levelValue),
            message,
            text,
            ...(normalizedMetadata ? { metadata: normalizedMetadata } : {}),
            ...(normalizedContext ? { context: normalizedContext } : {})
        };

        return {
            valid: true,
            errors: [],
            entry: normalizedEntry
        };
    }

    validateLogEntries(entries: JsonValue | null | undefined): EntriesValidationResult {
        if (!isArray(entries)) {
            throw new TypeError('Expected array of log entries');
        }

        const validEntries: LogEntry[] = [];
        const invalidEntries: { entry: JsonValue | null | undefined; errors: string[] }[] = [];

        for (const entry of entries) {
            const result = this.validateLogEntry(entry);
            if (result.valid && result.entry) {
                validEntries.push(result.entry);
            } else {
                invalidEntries.push({ entry, errors: result.errors });
            }
        }

        return {
            validEntries,
            invalidEntries
        };
    }

    validateLogLineLimit(limit: JsonValue | null | undefined): LogLineLimitResult {
        if (typeof limit !== 'number' || !Number.isInteger(limit)) {
            return {
                valid: false,
                limit: null,
                error: `Log line limit must be an integer, got ${getTypeOf(limit)}: ${String(limit)}`
            };
        }

        if (!VALID_LOG_LINE_LIMITS.includes(limit)) {
            return {
                valid: false,
                limit: null,
                error: `Invalid log line limit: ${limit}. Must be one of: ${VALID_LOG_LINE_LIMITS.join(', ')}`
            };
        }

        return {
            valid: true,
            limit: limit,
            error: null
        };
    }

    validateTextZoom(zoom: number | null | undefined): TextZoomResult {
        if (!isNumber(zoom) || !Number.isFinite(zoom)) {
            return {
                valid: false,
                zoom: null,
                error: `Text zoom must be a finite number, got ${getTypeOf(zoom)}: ${String(zoom)}`
            };
        }

        if (zoom < TEXT_ZOOM_MIN || zoom > TEXT_ZOOM_MAX) {
            return {
                valid: false,
                zoom: null,
                error: `Text zoom ${zoom} is outside the allowed range ${TEXT_ZOOM_MIN}-${TEXT_ZOOM_MAX}`
            };
        }

        return {
            valid: true,
            zoom: zoom,
            error: null
        };
    }

    validateReplayLimit(limit: JsonValue | null | undefined): ReplayLimitResult {
        if (typeof limit !== 'number' || !Number.isInteger(limit) || limit < 0) {
            return {
                valid: false,
                limit: 1000,
                error: `Replay limit must be a non-negative integer, got ${getTypeOf(limit)}: ${String(limit)}`
            };
        }

        if (limit > MAX_REPLAY_LIMIT) {
            return {
                valid: false,
                limit: MAX_REPLAY_LIMIT,
                error: `Replay limit ${limit} exceeds maximum ${MAX_REPLAY_LIMIT}`
            };
        }

        return {
            valid: true,
            limit: limit,
            error: null
        };
    }

    isValidLogLevel(level: string): boolean {
        return VALID_LOG_LEVEL_SET.has(toTrimmedUpper(level));
    }

    getValidLogLevels(): string[] {
        return VALID_LOG_LEVELS.slice();
    }

    strictValidate(entry: JsonValue | null | undefined): StrictValidationResult {
        const result = this.validateLogEntry(entry);
        if (!result.valid || !result.entry) {
            return {
                valid: false,
                errors: result.errors
            };
        }

        const errors: string[] = [];
        const logEntry = result.entry;

        if (!logEntry.metadata) {
            errors.push('metadata must be a non-null object');
        } else {
            const metadata = logEntry.metadata;
            if (!isString(metadata.hostname) || !metadata.hostname.trim()) {
                errors.push('metadata.hostname must be a non-empty string');
            }
            if (!isNumber(metadata.pid) || !Number.isFinite(metadata.pid)) {
                errors.push('metadata.pid must be a finite number');
            }
        }

        if (!logEntry.context) {
            errors.push('context must be a non-null object');
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }

    #isValidTimestamp(value: string): boolean {
        const timestamp = new Date(value).getTime();
        return Number.isFinite(timestamp);
    }
}

const LOG_VALIDATION_SERVICE_ID = 'core.logValidation';

const isLogDataValidator = <T>(value: T): value is T & LogDataValidator => {
    if (!isObject(value)) {
        return false;
    }
    return 'validateLogEntry' in value && isFunction(value.validateLogEntry) && 'validateLogEntries' in value && isFunction(value.validateLogEntries) && 'validateLogLineLimit' in value && isFunction(value.validateLogLineLimit) && 'validateTextZoom' in value && isFunction(value.validateTextZoom) && 'validateReplayLimit' in value && isFunction(value.validateReplayLimit) && 'isValidLogLevel' in value && isFunction(value.isValidLogLevel) && 'getValidLogLevels' in value && isFunction(value.getValidLogLevels) && 'strictValidate' in value && isFunction(value.strictValidate);
};

const createLogValidation = (): LogDataValidator => {
    const instance = new LogDataValidator();
    Object.freeze(instance);
    return instance;
};

const getLogValidation = (): LogDataValidator => {
    const candidate = resolveKernelService(LOG_VALIDATION_SERVICE_ID);
    if (!isLogDataValidator(candidate)) {
        throw new Error(`${LOG_VALIDATION_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { LogDataValidator, getLogValidation, createLogValidation, LOG_VALIDATION_SERVICE_ID, VALID_LOG_LEVELS, VALID_LOG_LINE_LIMITS, TEXT_ZOOM_MIN, TEXT_ZOOM_MAX };
