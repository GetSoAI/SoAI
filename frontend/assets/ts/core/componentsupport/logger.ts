/* SoAI - Shared component support logger [frontend/assets/ts/core/componentsupport/logger.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import type { LogLevel, Reporter } from '@core/componentsupport/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ErrorWithName } from '@core/types/streamTypes.ts';

const getReporter = (level: LogLevel): Reporter | null => {
    if (!isObject(errorHandler)) {
        return null;
    }
    const candidate = errorHandler[level];
    return isFunction(candidate) ? candidate : null;
};

const log = (level: LogLevel, context: string, message: string, error?: Error | ErrorWithName | JsonValue | null): void => {
    const reporter = getReporter(level);
    if (!reporter) return;
    reporter(context, message, error);
};

const logWarn = (context: string, message: string, error?: Error | ErrorWithName | JsonValue | null): void => log('warn', context, message, error);

const logError = (context: string, message: string, error?: Error | ErrorWithName | JsonValue | null): void => log('error', context, message, error);

const logDebug = (context: string, message: string, error?: Error | ErrorWithName | JsonValue | null): void => log('debug', context, message, error);

export { log, logDebug, logError, logWarn };
