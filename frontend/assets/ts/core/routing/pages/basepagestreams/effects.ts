/* SoAI - Shared routing base page streams effects [frontend/assets/ts/core/routing/pages/basepagestreams/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPerformance } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFunction, isString } from '@core/typeGuards.ts';
import type { BasePageStreamsTaskHost, BasePageStreamsTaskTelemetryContext, RunPageTaskOptions } from '@core/routing/pages/basepagestreams/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

const normalizeTelemetryContext = (source: Record<string, JsonValue | null | undefined>): JsonObject => {
    const normalized: JsonObject = {};
    for (const [key, value] of Object.entries(source)) {
        if (value !== undefined) {
            normalized[key] = value;
        }
    }
    return normalized;
};

const buildTaskTelemetryContext = <T>(host: BasePageStreamsTaskHost, stepName: string, options: RunPageTaskOptions<T>): BasePageStreamsTaskTelemetryContext => {
    const telemetryContext = normalizeTelemetryContext({ pageId: host.pageId, step: stepName, ...(options.telemetryContext || {}) });
    const telemetryTags = Array.from(new Set(['pageTask', host.pageId, stepName, ...[options.telemetryTags].flat().filter(isString)]));
    const label = options.displayName?.trim() || stepName;
    return { context: telemetryContext, tags: telemetryTags, label };
};

const runPageTask = async <T>(host: BasePageStreamsTaskHost, name: string, operation: () => Promise<T>, options: RunPageTaskOptions<T> = {}): Promise<T | null> => {
    if (!isString(name)) {
        throw err('Step name required');
    }
    if (!isFunction(operation)) {
        throw err('Operation required');
    }

    const loadingElement = options.loadingElement;
    const loadingText = options.loadingText;
    if (loadingElement) {
        host.setLoadingState(loadingElement, true, loadingText && isString(loadingText) ? loadingText : i18n.t('common.loading'));
    }

    const stepName = name.trim();
    const telemetryHost = host.pageContext.telemetry;
    const telemetryContext = buildTaskTelemetryContext(host, stepName, options);
    const startTime = getPerformance().now();

    const emitTelemetry = (severity: string, message: string, extra: { context?: JsonObject; duration?: number; data?: JsonObject } = {}): void => {
        telemetryHost?.emit?.({
            severity,
            module: options.telemetryModuleId?.trim() || `pages.${host.pageId}`,
            message,
            stage: stepName,
            tags: telemetryContext.tags,
            context: extra.context ?? telemetryContext.context,
            ...extra
        });
    };

    emitTelemetry('info', `${telemetryContext.label} started`, { context: telemetryContext.context });

    try {
        const result = await operation();
        emitTelemetry('info', `${telemetryContext.label} completed`, {
            duration: getPerformance().now() - startTime,
            context: telemetryContext.context
        });
        if (options.successMessage) {
            host.showNotification(options.successMessage, 'success');
        }
        await options.onSuccess?.(result);
        return result;
    } catch (error) {
        const runtimeError = ensureError(error);
        const messageValue = runtimeError.message;
        const codeValue = hasOwn(runtimeError, 'code') && 'code' in runtimeError ? runtimeError.code : null;
        const errorMessage = isString(messageValue) ? messageValue : runtimeError.message;
        const errorCode = isString(codeValue) ? codeValue : null;

        emitTelemetry('error', `${telemetryContext.label} failed`, {
            duration: getPerformance().now() - startTime,
            data: { error: { message: errorMessage ?? null, code: errorCode ?? null } },
            context: telemetryContext.context
        });

        errorHandler.error(host.pageId, `${telemetryContext.label} failed`, runtimeError);
        const handledByNotifier = notifyHandledOperationError(runtimeError);
        if (!handledByNotifier) {
            const toastMessage = options.errorToastMessage ?? i18n.t('common.errors.operationFailed');
            host.showNotification(toastMessage, 'error');
        }

        await options.onError?.(runtimeError);
        if (options.rethrow !== false) {
            throw runtimeError;
        }
        return null;
    } finally {
        if (loadingElement) {
            host.setLoadingState(loadingElement, false);
        }
        await options.onFinally?.();
    }
};

export { runPageTask };
