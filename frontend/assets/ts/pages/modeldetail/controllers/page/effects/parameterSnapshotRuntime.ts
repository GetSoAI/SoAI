/* SoAI - Model detail parameter snapshot acceptance and recovery [frontend/assets/ts/pages/modeldetail/controllers/page/effects/parameterSnapshotRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { SnapshotError, SnapshotProtocolError } from '@core/websocketclient/service.ts';
import { PARAMETER_SNAPSHOT_CACHE, PARAMETER_STORAGE_PREFIX, readSnapshotEntry } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailEffectsHost, ParametersData } from '@pages/modeldetail/controllers/page/effects/types.ts';
import { decodeModelDetailParameterPayload } from '@pages/modeldetail/mappers/ModelDetailParameterPayloadDomain.ts';
import { fetchParametersViaWebSocketSnapshot } from '@pages/modeldetail/services/modelDetailSnapshotFetch.ts';
import type { ParameterSnapshotOutcome, ParameterUnavailableReason } from '@pages/modeldetail/state/ModelDetailParameterAuthorityState.ts';

interface CachedModelDetailParameters {
    payload: ParametersData;
    timestampMs: number | null;
}

const PARAMETER_RECOVERY_DELAYS_MS: readonly number[] = [1000, 2000];
const RETRYABLE_SNAPSHOT_ERROR_CODES = new Set(['model_parameter_schema_unavailable', 'service_unavailable', 'timeout_error']);

const readParameterFailureReason = (error: Error): ParameterUnavailableReason => {
    if (error instanceof SnapshotError && error.code === 'model_parameter_schema_unavailable' && isJsonObject(error.payload)) {
        const details = error.payload['details'];
        const reason = isJsonObject(details) ? details['reason'] : null;
        if (reason === 'plugin_operation_in_progress' || reason === 'plugin_unregistered') return reason;
    }
    return 'refresh_failed';
};

const isRetryableParameterFailure = (error: Error): boolean => {
    if (error instanceof SnapshotError) return error.code !== undefined && RETRYABLE_SNAPSHOT_ERROR_CODES.has(error.code);
    return !(error instanceof SnapshotProtocolError || error instanceof TypeError);
};

const readCachedModelDetailParameters = (modelId: string): CachedModelDetailParameters | null => {
    const entry = readSnapshotEntry(PARAMETER_STORAGE_PREFIX, modelId);
    const memoryPayload = entry === null ? PARAMETER_SNAPSHOT_CACHE.get(modelId) : null;
    if (entry === null) return memoryPayload ? { payload: memoryPayload, timestampMs: null } : null;
    try {
        const timestampMs = isFiniteNumber(entry.timestamp) && entry.timestamp <= Date.now() ? entry.timestamp : null;
        return { payload: decodeModelDetailParameterPayload(entry.value), timestampMs };
    } catch (error) {
        errorHandler.warn('ModelDetailPage', 'Discarding invalid cached parameter snapshot', { id: modelId, error: ensureError(error) });
        return null;
    }
};

const isParameterSessionCurrent = (host: ModelDetailEffectsHost, token: number, modelId: string): boolean => host.state.signal?.aborted !== true && !host.state.isDestroyed && host.state.parameterAuthority.reads.isActive(token) && host.state.modelId === modelId;

const applyModelDetailParameters = (host: ModelDetailEffectsHost, payload: ParametersData, displayedAtMs: number | null, validated: boolean): void => {
    host.state.parameterAuthority.recordApplied(payload, displayedAtMs, validated);
    host.rendering.applyParametersPayload(payload);
    if (host.state.activeTab === 'parameters') host.rendering.renderParametersInterface();
    host.rendering.renderParameterAvailability();
    host.rendering.notifySaveChanged();
};

const showCachedModelDetailParameters = (host: ModelDetailEffectsHost, cached: CachedModelDetailParameters): void => {
    host.state.parameterAuthority.status = 'stale';
    applyModelDetailParameters(host, cached.payload, cached.timestampMs, false);
};

const acceptModelDetailParameters = (host: ModelDetailEffectsHost, token: number, modelId: string, payload: ParametersData): void => {
    const authority = host.state.parameterAuthority;
    const receivedAtMs = Date.now();
    PARAMETER_SNAPSHOT_CACHE.set(modelId, payload);
    host.rendering.persistSnapshots(null, payload);
    authority.status = 'current';
    authority.reason = null;
    authority.exhaustionNotified = false;
    if (!authority.saving && host.state.parametersData !== null && authority.matchesAppliedSchema(payload)) {
        host.rendering.mergeParametersPayload(payload);
        authority.recordApplied(payload, receivedAtMs, true);
        host.rendering.renderParameterAvailability();
        host.rendering.notifySaveChanged();
        return;
    }
    if (authority.saving || (host.state.parametersData !== null && host.state.isParameterEditorDirty())) {
        authority.validated = true;
        authority.holdPending(token, payload, receivedAtMs);
        host.rendering.renderParameterAvailability();
        host.rendering.notifySaveChanged();
        return;
    }
    applyModelDetailParameters(host, payload, receivedAtMs, true);
};

const markModelDetailParametersUnavailable = (host: ModelDetailEffectsHost, modelId: string, error: Error): void => {
    const authority = host.state.parameterAuthority;
    authority.status = 'unavailable';
    authority.reason = readParameterFailureReason(error);
    if (!isRetryableParameterFailure(error)) PARAMETER_SNAPSHOT_CACHE.delete(modelId);
    host.rendering.renderParameterAvailability();
    host.rendering.notifySaveChanged();
    if (!authority.exhaustionNotified) {
        authority.exhaustionNotified = true;
        host.rendering.notifyParametersUnavailable(i18n.t('modelDetail.parameterAvailability.unavailableNotice'));
    }
};

const runModelDetailParameterRecovery = async (host: ModelDetailEffectsHost, modelId: string, isCurrent: () => boolean): Promise<ParameterSnapshotOutcome> => {
    const authority = host.state.parameterAuthority;
    const deadline = monotonicMs() + TIMEOUTS.API_REQUEST;
    for (let attempt = 0; attempt <= PARAMETER_RECOVERY_DELAYS_MS.length; attempt += 1) {
        if (!isCurrent()) return 'cancelled';
        if (authority.saving) return 'stale';
        const token = authority.reads.next();
        const generation = authority.invalidationGeneration;
        if (authority.status !== 'unavailable') authority.status = 'refreshing';
        host.rendering.renderParameterAvailability();
        try {
            if (!isCurrent()) return 'cancelled';
            const timeoutMs = deadline - monotonicMs();
            if (timeoutMs <= 0) break;
            const payload = await fetchParametersViaWebSocketSnapshot({ modelId, model: host.state.model, signal: host.state.signal ?? undefined, timeoutMs });
            if (!isCurrent()) return 'cancelled';
            if (authority.saving) return 'stale';
            if (monotonicMs() >= deadline) break;
            if (isParameterSessionCurrent(host, token, modelId) && generation === authority.invalidationGeneration) {
                acceptModelDetailParameters(host, token, modelId, payload);
                if (isCurrent() && isParameterSessionCurrent(host, token, modelId) && generation === authority.invalidationGeneration) return 'reconciled';
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isCurrent() || isAbortError(runtimeError)) return 'cancelled';
            if (authority.saving) return 'stale';
            if (generation === authority.invalidationGeneration) {
                errorHandler.debug('ModelDetailPage', 'Parameter snapshot request failed', { id: modelId, attempt, error: runtimeError });
                if (PARAMETER_RECOVERY_DELAYS_MS[attempt] === undefined || !isRetryableParameterFailure(runtimeError)) {
                    authority.reconciliationExhausted = true;
                    markModelDetailParametersUnavailable(host, modelId, runtimeError);
                    return 'unavailable';
                }
                const failureReason = readParameterFailureReason(runtimeError);
                if (failureReason !== 'refresh_failed') {
                    authority.status = 'unavailable';
                    authority.reason = failureReason;
                    host.rendering.renderParameterAvailability();
                    host.rendering.notifySaveChanged();
                }
            }
        }
        const delayMs = PARAMETER_RECOVERY_DELAYS_MS[attempt];
        const remainingMs = deadline - monotonicMs();
        if (delayMs === undefined || remainingMs <= 0) break;
        await waitForTimerDelay(getWindow(), Math.min(delayMs, remainingMs), host.state.signal);
    }
    if (!isCurrent()) return 'cancelled';
    authority.reconciliationExhausted = true;
    markModelDetailParametersUnavailable(host, modelId, new Error('Parameter reconciliation remained stale within its recovery deadline.'));
    return 'stale';
};

const refreshModelDetailParameters = async (host: ModelDetailEffectsHost, options: { force?: boolean } = {}): Promise<ParameterSnapshotOutcome> => {
    const authority = host.state.parameterAuthority;
    const modelId = host.state.modelId;
    if (!modelId || host.state.model?.type === 'virtual') return 'cancelled';
    if (!host.state.model) return 'stale';
    if (options.force) {
        markModelDetailParametersStale(host);
    }
    if (authority.recovery) return await authority.recovery;
    if (authority.saving) return 'stale';
    authority.reconciliationExhausted = false;
    const completion = createDeferred<ParameterSnapshotOutcome>();
    authority.recovery = completion.promise;
    const isCurrent = (): boolean => authority.recovery === completion.promise && host.state.signal?.aborted !== true && !host.state.isDestroyed && host.state.modelId === modelId;
    void runModelDetailParameterRecovery(host, modelId, isCurrent).then(
        (outcome) => {
            if (authority.recovery === completion.promise) authority.recovery = null;
            completion.resolve(outcome);
        },
        (error) => {
            if (authority.recovery === completion.promise) authority.recovery = null;
            completion.reject(ensureError(error));
        }
    );
    return await completion.promise;
};

const markModelDetailParametersStale = (host: ModelDetailEffectsHost): void => {
    const authority = host.state.parameterAuthority;
    authority.invalidate();
    if (authority.status === 'unavailable' || authority.status === 'stale' || host.state.parametersData === null) return;
    authority.status = 'stale';
    host.rendering.renderParameterAvailability();
};

const invalidateModelDetailParameters = async (host: ModelDetailEffectsHost): Promise<ParameterSnapshotOutcome> => {
    const authority = host.state.parameterAuthority;
    markModelDetailParametersStale(host);
    if (authority.saving || authority.reconciliationExhausted) return 'stale';
    return await refreshModelDetailParameters(host);
};

const beginModelDetailParameterSave = (host: ModelDetailEffectsHost): void => {
    const authority = host.state.parameterAuthority;
    authority.invalidate();
    authority.pending = null;
    authority.saving = true;
};

const finishModelDetailParameterSave = (host: ModelDetailEffectsHost): Promise<ParameterSnapshotOutcome> => {
    const authority = host.state.parameterAuthority;
    authority.saving = false;
    authority.pending = null;
    return refreshModelDetailParameters(host, { force: true });
};

const applyPendingModelDetailParameters = (host: ModelDetailEffectsHost, options: { discard?: boolean } = {}): boolean => {
    const authority = host.state.parameterAuthority;
    const pending = authority.pending;
    if (pending === null || authority.saving || !authority.reads.isActive(pending.token)) return false;
    if (!options.discard && host.state.isParameterEditorDirty()) return false;
    applyModelDetailParameters(host, pending.payload, pending.receivedAtMs, true);
    return true;
};

export { applyPendingModelDetailParameters, beginModelDetailParameterSave, finishModelDetailParameterSave, invalidateModelDetailParameters, markModelDetailParametersStale, readCachedModelDetailParameters, refreshModelDetailParameters, showCachedModelDetailParameters };
export type { CachedModelDetailParameters };
