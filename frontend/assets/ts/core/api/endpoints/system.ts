/* SoAI - Shared API system [frontend/assets/ts/core/api/endpoints/system.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeNonEmptyString } from '@core/api/apiNormalizers.ts';
import { decodeAcceptedPowerActionResponse, decodeActivePowerOperationResponse, decodePowerOperationResponse, type AcceptedPowerActionResponse, type PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import { decodeSuccessfulMutationResponse, type SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { decodeSystemMetricsResponse, type SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import { decodeSystemLimits, type SystemLimits } from '@core/api/contracts/systemLimitsContracts.ts';
import { decodeCancellationRegistryReset, decodeCancellationRegistrySweep, decodeCircuitBreakerSnapshot, decodeInstanceNameResponse, decodeRawResponse, decodeRequirementsText, decodeResetMessage, decodeSecurityHardeningAudit, decodeSystemHealth, decodeSystemInfo, decodeSystemLicense, decodeSystemLogSnapshot, decodeSystemLogSources, decodeSystemStateDefinitions, decodeSystemStatus, decodeTaskCancellation, serializeInstanceNameUpdateRequest, type CancellationRegistryResetResponse, type CancellationRegistrySweepResponse, type CircuitBreakerSnapshot, type InstanceNameResponse, type MessageResponse, type SecurityHardeningAudit, type SystemHealthResponse, type SystemInfoResponse, type SystemLicenseResponse, type SystemLogSnapshot, type SystemLogSourcesResponse, type SystemStateDefinitionsResponse, type SystemStatusResponse, type TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { getUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';

interface SystemEndpoints {
    health: (options?: RequestOptions) => Promise<SystemHealthResponse>;
    updateInstanceName: (instanceName: string | null, options?: RequestOptions) => Promise<InstanceNameResponse>;
    info: (options?: RequestOptions) => Promise<SystemInfoResponse>;
    license: () => Promise<SystemLicenseResponse>;
    requirements: () => Promise<string>;
    status: () => Promise<SystemStatusResponse>;
    securityHardeningAudit: (options?: RequestOptions) => Promise<SecurityHardeningAudit>;
    metrics: () => Promise<SystemMetricsResponse>;
    limits: () => Promise<SystemLimits>;
    stateDefinitions: () => Promise<SystemStateDefinitionsResponse>;
    resetMetrics: () => Promise<MessageResponse>;
    resetHardwareHistory: () => Promise<MessageResponse>;
    resetCircuitBreaker: (pluginName: string) => Promise<SuccessfulMutationResponse>;
    cancellations: { resetRegistry: () => Promise<CancellationRegistryResetResponse>; sweepRegistry: () => Promise<CancellationRegistrySweepResponse>; cancelAll: () => never };
    cancelTask: (taskId: string, reason?: string | null) => Promise<TaskCancellationResponse>;
    checkCircuitBreaker: (pluginName: string) => Promise<CircuitBreakerSnapshot>;
    logs: (source: string, options?: RequestOptions) => Promise<SystemLogSnapshot>;
    logSources: (options?: RequestOptions) => Promise<SystemLogSourcesResponse>;
    testSuite: () => Promise<Response>;
    power: { restartApplication: (payload?: { delay?: number }) => Promise<AcceptedPowerActionResponse>; shutdownApplication: (payload?: { delay?: number }) => Promise<AcceptedPowerActionResponse>; shutdown: (payload?: { delay?: number; force?: boolean }) => Promise<AcceptedPowerActionResponse>; reboot: (payload?: { delay?: number; force?: boolean }) => Promise<AcceptedPowerActionResponse>; suspend: (payload?: { delay?: number; force?: boolean }) => Promise<AcceptedPowerActionResponse>; hibernate: (payload?: { delay?: number; force?: boolean }) => Promise<AcceptedPowerActionResponse>; active: () => Promise<PowerOperationResponse | null>; get: (operationId: string) => Promise<PowerOperationResponse>; cancel: (operationId: string) => Promise<PowerOperationResponse> };
}

const createSystemEndpoints = (api: ApiClientContext): SystemEndpoints => {
    return {
        health: async (options: RequestOptions = {}): Promise<SystemHealthResponse> => decodeSystemHealth(await api.get('/api/v1/system/health', options)),
        updateInstanceName: async (instanceName: string | null, options: RequestOptions = {}): Promise<InstanceNameResponse> => decodeInstanceNameResponse(await api.put('/api/v1/system/instance-name', serializeInstanceNameUpdateRequest(instanceName), options)),
        info: async (options: RequestOptions = {}): Promise<SystemInfoResponse> => decodeSystemInfo(await api.get('/api/v1/system/info', options)),
        license: async (): Promise<SystemLicenseResponse> => decodeSystemLicense(await api.get('/api/v1/system/license')),
        requirements: async (): Promise<string> => decodeRequirementsText(await api.get('/api/v1/system/requirements')),
        status: async (): Promise<SystemStatusResponse> => decodeSystemStatus(await api.get('/api/v1/system/status')),
        securityHardeningAudit: async (options: RequestOptions = {}): Promise<SecurityHardeningAudit> => decodeSecurityHardeningAudit(await api.get('/api/v1/system/security/hardening', options)),
        metrics: async (): Promise<SystemMetricsResponse> => decodeSystemMetricsResponse(await api.get('/api/v1/metrics')),
        limits: async (): Promise<SystemLimits> => decodeSystemLimits(await api.get('/api/v1/system/limits')),
        stateDefinitions: async (): Promise<SystemStateDefinitionsResponse> => decodeSystemStateDefinitions(await api.get('/api/v1/system/states')),
        resetMetrics: async (): Promise<MessageResponse> => decodeResetMessage(await api.post('/api/v1/system/metrics/reset'), 'System metrics reset response'),
        resetHardwareHistory: async (): Promise<MessageResponse> => decodeResetMessage(await api.post('/api/v1/system/hardware/history/reset'), 'Hardware history reset response'),
        resetCircuitBreaker: async (pluginName: string): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.post(`/api/v1/system/plugins/${api.encodePathSegment(pluginName)}/reset-circuit-breaker`), 'Plugin circuit breaker reset response'),
        cancellations: {
            resetRegistry: async (): Promise<CancellationRegistryResetResponse> => decodeCancellationRegistryReset(await api.post('/api/v1/tasks/cancellations/reset')),
            sweepRegistry: async (): Promise<CancellationRegistrySweepResponse> => decodeCancellationRegistrySweep(await api.post('/api/v1/tasks/cancellations/sweep')),
            cancelAll: (): never => {
                throw new Error('Cancel-all is disabled in WebUI for safety. Use REST API: POST /api/v1/tasks/cancel-all');
            }
        },
        cancelTask: async (taskId: string, reason: string | null = null): Promise<TaskCancellationResponse> => {
            const trimmedId = toTrimmedString(taskId);
            if (!trimmedId) throw new Error('cancelTask requires a taskId');
            return decodeTaskCancellation(
                await api.post(`/api/v1/tasks/${api.encodePathSegment(trimmedId)}/cancel`, {
                    reason: normalizeNonEmptyString(reason) || getUserCancellationReason()
                })
            );
        },
        checkCircuitBreaker: async (pluginName: string): Promise<CircuitBreakerSnapshot> => decodeCircuitBreakerSnapshot(await api.get(`/api/v1/system/plugins/${api.encodePathSegment(pluginName)}/check-circuit-breaker`)),
        logs: async (source: string, options: RequestOptions = {}): Promise<SystemLogSnapshot> => decodeSystemLogSnapshot(await api.get(`/api/v1/system/logs/${api.encodePathSegment(source)}`, options)),
        logSources: async (options: RequestOptions = {}): Promise<SystemLogSourcesResponse> => decodeSystemLogSources(await api.get('/api/v1/system/logs/sources', options)),
        testSuite: async (): Promise<Response> => decodeRawResponse(await api.get('/api/v1/system/test-suite', { rawResponse: true }), 'System test suite response'),
        power: {
            restartApplication: async (payload: { delay?: number } = {}): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/restart-application', payload, powerMutationOptions())),
            shutdownApplication: async (payload: { delay?: number } = {}): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/shutdown-application', payload, powerMutationOptions())),
            shutdown: async (payload: { delay?: number; force?: boolean } = { delay: 0, force: false }): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/shutdown', payload, powerMutationOptions())),
            reboot: async (payload: { delay?: number; force?: boolean } = { delay: 0, force: false }): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/reboot', payload, powerMutationOptions())),
            suspend: async (payload: { delay?: number; force?: boolean } = { delay: 0, force: false }): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/suspend', payload, powerMutationOptions())),
            hibernate: async (payload: { delay?: number; force?: boolean } = { delay: 0, force: false }): Promise<AcceptedPowerActionResponse> => decodeAcceptedPowerActionResponse(await api.post('/api/v1/system/power/hibernate', payload, powerMutationOptions())),
            active: async (): Promise<PowerOperationResponse | null> => decodeActivePowerOperationResponse(await api.get('/api/v1/system/power/operations/active')),
            get: async (operationId: string): Promise<PowerOperationResponse> => decodePowerOperationResponse(await api.get(`/api/v1/system/power/operations/${api.encodePathSegment(operationId)}`)),
            cancel: async (operationId: string): Promise<PowerOperationResponse> => decodePowerOperationResponse(await api.post(`/api/v1/system/power/operations/${api.encodePathSegment(operationId)}/cancel`))
        }
    };
};

const powerMutationOptions = (): RequestOptions => ({
    headers: { 'Idempotency-Key': createMutationRequestId() }
});

export { createSystemEndpoints };
export type { SystemEndpoints };
