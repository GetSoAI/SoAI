/* SoAI - Shared frontend connection status mapping [frontend/assets/ts/core/connectionstatus/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isObject, isString } from '@core/typeGuards.ts';
import { CONNECTED_EVENT_THROTTLE_MS, EVT_DISCO, EVT_UPDATE, INITIAL_RESTART_DELAY_MS, STREAM_METRIC_STAGE_CONNECTED, STREAM_TELEMETRY_STAGE_CONNECTED } from '@core/connectionstatus/constants.ts';
import { updateRestartInfo } from '@core/connectionstatus/actions.ts';
import { flushWaiters, notifyRestartSubscribers, rejectWaiters } from '@core/connectionstatus/events.ts';
import { extractSystemInfo, extractSystemState, mergeStatus, normalizeStatusPayload, readSnapshotMeta } from '@core/connectionstatus/health.ts';

import type { SnapshotProcessingHost } from '@core/connectionstatus/internalContracts.ts';

const processConnectionStatusSnapshot = (host: SnapshotProcessingHost, snapshot: JsonValue, eventType: string): void => {
    const state = host.state;
    if (eventType !== EVT_DISCO) {
        host.clearRestartTimer();
        state.nextRestartDelayMs = INITIAL_RESTART_DELAY_MS;
    }

    if (eventType === EVT_DISCO) {
        const wasConnected = state.connected;
        const queueDepth = host.readQueueDepth();
        host.publishMetric('connection:lost', { reason: 'stream-event' }, queueDepth);
        host.setConnected(false);

        if (wasConnected) {
            const waiters = state.waiters.length;
            host.emitConnectionError(new Error('System status stream disconnected'), 'System status stream disconnected');
            host.emitEvent(EVT_DISCO, { raw: snapshot, error: null });
            host.setConnected(false);
            host.emitTelemetry({
                stage: 'connection:lost',
                message: 'System status stream disconnected',
                severity: 'warn',
                data: { waiters },
                queueDepth
            });
        }

        host.resetRestartInfoState({ reason: 'stream-event-disconnected' });
        if (state.waiters.length) {
            rejectWaiters(state, new Error('Connection status stream disconnected'));
        }
        host.scheduleStreamRestart();
        return;
    }

    if (!snapshot) {
        host.log('warn', 'Empty snapshot received');
        return;
    }

    const payload: JsonValue | undefined = isObject(snapshot) && hasOwn(snapshot, 'value') ? snapshot['value'] : snapshot;
    const normalized = normalizeStatusPayload(payload);
    const meta = readSnapshotMeta(snapshot);
    const cached = (isObject(snapshot) && snapshot['cached'] === true) || Boolean(meta && (meta.cached === true || meta.source === 'cache' || meta.origin === 'cache'));

    const hadStatus = Boolean(state.currentStatus);

    if (normalized) {
        state.currentStatus = mergeStatus(state.currentStatus, normalized);
        state.systemInfo = extractSystemInfo(payload, normalized);
        flushWaiters(state);
    }

    const systemState = extractSystemState(normalized) || extractSystemState(payload);
    const snapshotStatus = isObject(snapshot) && isString(snapshot['status']) ? snapshot['status'] : null;

    const changed = updateRestartInfo(state, systemState, {
        normalizedPayload: normalized,
        rawPayload: payload,
        snapshotStatus,
        eventType
    });
    if (changed) {
        notifyRestartSubscribers(state);
    }

    const wasConnected = state.connected;
    host.setConnected(true);

    const queueDepth = host.readQueueDepth();
    const telemetryData = {
        eventType,
        normalizedKeys: normalized ? Object.keys(normalized) : null,
        cached,
        waiters: state.waiters.length
    };

    const stage = hadStatus ? 'snapshot:update' : 'snapshot:initial';
    if (cached) {
        host.emitTelemetry({
            stage: 'snapshot:cache-hit',
            message: 'Processed cached system status snapshot',
            severity: 'debug',
            data: telemetryData,
            queueDepth
        });
    }

    host.emitTelemetry({
        stage,
        message: hadStatus ? 'System status snapshot updated' : 'System status snapshot initialized',
        severity: 'info',
        data: telemetryData,
        queueDepth
    });
    host.publishMetric(stage, { cached }, queueDepth);
    host.emitEvent(eventType || EVT_UPDATE, { raw: snapshot });

    if (!wasConnected) {
        const now = Date.now();
        if (!state.lastConnectedEmitTimestamp || now - state.lastConnectedEmitTimestamp >= CONNECTED_EVENT_THROTTLE_MS) {
            state.lastConnectedEmitTimestamp = now;
            host.emitEvent('connected', { raw: snapshot });
            host.emitTelemetry({
                stage: STREAM_TELEMETRY_STAGE_CONNECTED,
                message: 'System status stream connected',
                severity: 'info',
                data: telemetryData,
                queueDepth
            });
            host.publishMetric(STREAM_METRIC_STAGE_CONNECTED, { cached }, queueDepth);
        }
    }
};

export { processConnectionStatusSnapshot };
