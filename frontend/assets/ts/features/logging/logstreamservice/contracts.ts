/* SoAI - Logging feature log stream service boundary contracts [frontend/assets/ts/features/logging/logstreamservice/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler, type ErrorHandler } from '@core/errorHandler.ts';
import { getLogNormalization, type LogNormalizer } from '@core/logNormalization.ts';
import { getLogValidation, LOG_VALIDATION_SERVICE_ID, type LogDataValidator } from '@core/logvalidation/public.ts';
import { getMaintenanceCoordinator, type MaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { getStateManager, type StateManager } from '@core/state/public.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { TelemetryService, TelemetryValue } from '@core/telemetry/contracts.ts';
import { isFunction } from '@core/typeGuards.ts';

type ErrorHandlerLevel = 'debug' | 'info' | 'warn' | 'error' | 'fatal';

interface LogStreamRuntimeDependencies {
    errorHandler: ErrorHandler;
    normalizer: LogNormalizer;
    validator: LogDataValidator;
    telemetry: TelemetryService;
    stateService: StateManager;
    maintenanceCoordinator: MaintenanceCoordinator;
}

interface LogStreamLogger {
    logError: (message: string, detail?: TelemetryValue) => void;
    logWarn: (message: string, detail?: TelemetryValue) => void;
    logDebug: (message: string, detail?: TelemetryValue) => void;
}

const createLogStreamRuntimeDependencies = (): LogStreamRuntimeDependencies => {
    const dependencies: LogStreamRuntimeDependencies = {
        errorHandler,
        normalizer: getLogNormalization(),
        validator: getLogValidation(),
        telemetry,
        stateService: getStateManager(),
        maintenanceCoordinator: getMaintenanceCoordinator()
    };

    if (!isFunction(dependencies.errorHandler.error)) {
        throw new Error('SoAI error handler must load before LogStreamService');
    }
    if (!isFunction(dependencies.telemetry.publishMetric)) {
        throw new Error('Telemetry service must expose publishMetric before LogStreamService');
    }
    if (!isFunction(dependencies.normalizer.normalizeLogEntry)) {
        throw new Error('core.logNormalization must expose normalizeLogEntry before LogStreamService');
    }
    if (!isFunction(dependencies.validator.validateLogEntry) || !isFunction(dependencies.validator.validateReplayLimit)) {
        throw new Error(`${LOG_VALIDATION_SERVICE_ID} must expose validation APIs before LogStreamService`);
    }
    if (!isFunction(dependencies.stateService.getTabState) || !isFunction(dependencies.stateService.setTabState) || !isFunction(dependencies.stateService.subscribeTabState)) {
        throw new Error('State manager must provide tab state accessors before LogStreamService');
    }
    if (!isFunction(dependencies.maintenanceCoordinator.subscribe) || !isFunction(dependencies.maintenanceCoordinator.getState)) {
        throw new Error('Maintenance coordinator must expose state subscriptions before LogStreamService');
    }

    return dependencies;
};

const createLogStreamLogger = (handler: ErrorHandler): LogStreamLogger => {
    const emitToHandler = (level: ErrorHandlerLevel, message: string, detail: TelemetryValue): void => {
        const reporterMap = handler;
        const reporter = reporterMap[level];
        if (isFunction(reporter)) {
            reporterMap[level]('LogStream', message, detail);
            return;
        }
        if (level !== 'error' && isFunction(handler.error)) {
            handler.error('LogStream', `[${level}] ${message}`, detail ?? null);
        }
    };

    return {
        logError: (message: string, detail?: TelemetryValue): void => {
            emitToHandler('error', message, detail);
        },
        logWarn: (message: string, detail?: TelemetryValue): void => {
            emitToHandler('warn', message, detail);
        },
        logDebug: (message: string, detail?: TelemetryValue): void => {
            emitToHandler('debug', message, detail);
        }
    };
};

export { createLogStreamLogger, createLogStreamRuntimeDependencies };
export type { LogStreamLogger, LogStreamRuntimeDependencies };
