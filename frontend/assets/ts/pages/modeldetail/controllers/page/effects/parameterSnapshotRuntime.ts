/* SoAI - Model detail parameter snapshot acceptance and recovery [frontend/assets/ts/pages/modeldetail/controllers/page/effects/parameterSnapshotRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { SnapshotError, SnapshotProtocolError } from '@core/websocketclient/service.ts';
import { PARAMETER_SNAPSHOT_CACHE, PARAMETER_STORAGE_PREFIX, readSnapshotEntry } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailEffectsHost, ParametersData } from '@pages/modeldetail/controllers/page/effects/types.ts';
import { decodeModelDetailParameterPayload } from '@pages/modeldetail/mappers/ModelDetailParameterPayloadDomain.ts';
import { fetchParametersViaWebSocketSnapshot } from '@pages/modeldetail/services/modelDetailSnapshotFetch.ts';
import type { ParameterUnavailableReason } from '@pages/modeldetail/state/ModelDetailParameterAuthorityState.ts';

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

const runModelDetailParameterRecovery = async (host: ModelDetailEffectsHost, modelId: string): Promise<void> => {
    const authority = host.state.parameterAuthority;
    for (let attempt = 0; ; attempt += 1) {
        const token = authority.reads.next();
        if (authority.status !== 'unavailable') authority.status = 'refreshing';
        host.rendering.renderParameterAvailability();
        try {
            const payload = await fetchParametersViaWebSocketSnapshot({ modelId, model: host.state.model });
            if (isParameterSessionCurrent(host, token, modelId)) acceptModelDetailParameters(host, token, modelId, payload);
            return;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isParameterSessionCurrent(host, token, modelId) || isAbortError(runtimeError)) return;
            errorHandler.debug('ModelDetailPage', 'Parameter snapshot request failed', { id: modelId, attempt, error: runtimeError });
            const delayMs = PARAMETER_RECOVERY_DELAYS_MS[attempt];
            if (delayMs === undefined || !isRetryableParameterFailure(runtimeError)) {
                markModelDetailParametersUnavailable(host, modelId, runtimeError);
                return;
            }
            const failureReason = readParameterFailureReason(runtimeError);
            if (failureReason !== 'refresh_failed') {
                authority.status = 'unavailable';
                authority.reason = failureReason;
                host.rendering.renderParameterAvailability();
                host.rendering.notifySaveChanged();
            }
            await waitForTimerDelay(getWindow(), delayMs, host.state.signal);
            if (!isParameterSessionCurrent(host, token, modelId)) return;
        }
    }
};

const refreshModelDetailParameters = async (host: ModelDetailEffectsHost, options: { force?: boolean } = {}): Promise<void> => {
    const authority = host.state.parameterAuthority;
    const modelId = host.state.modelId;
    if (!modelId || host.state.model?.type === 'virtual') return;
    if (authority.recovery && !options.force) {
        await authority.recovery;
        return;
    }
    if (options.force) authority.reads.invalidate();
    const recovery = runModelDetailParameterRecovery(host, modelId).finally(() => {
        if (authority.recovery === recovery) authority.recovery = null;
    });
    authority.recovery = recovery;
    await recovery;
};

const markModelDetailParametersStale = (host: ModelDetailEffectsHost): void => {
    const authority = host.state.parameterAuthority;
    if (authority.status === 'unavailable' || host.state.parametersData === null) return;
    authority.status = 'stale';
    host.rendering.renderParameterAvailability();
};

const beginModelDetailParameterSave = (host: ModelDetailEffectsHost): void => {
    const authority = host.state.parameterAuthority;
    authority.reads.invalidate();
    authority.pending = null;
    authority.saving = true;
};

const finishModelDetailParameterSave = (host: ModelDetailEffectsHost): Promise<void> => {
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

export { applyPendingModelDetailParameters, beginModelDetailParameterSave, finishModelDetailParameterSave, markModelDetailParametersStale, readCachedModelDetailParameters, refreshModelDetailParameters, showCachedModelDetailParameters };
export type { CachedModelDetailParameters };
