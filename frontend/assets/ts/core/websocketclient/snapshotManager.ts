/* SoAI - Shared frontend WebSocket client snapshot manager [frontend/assets/ts/core/websocketclient/snapshotManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { SNAPSHOT_TIMEOUT_MS, SNAPSHOT_TIMEOUT_MESSAGE_PREFIX } from '@core/websocketclient/constants.ts';
import { resolveSnapshotErrorMessage, resolveSnapshotId, resolveSnapshotTraceId, serializeSnapshotRequest } from '@core/websocketclient/events.ts';
import { type PendingSnapshot, type SnapshotRequestOptions, type SnapshotResponseEnvelope, type WebSocketMessageData } from '@core/websocketclient/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';

class SnapshotError extends Error {
    payload: JsonValue | undefined;
    traceId: string | undefined;

    constructor(message: string, payload: JsonValue | undefined = undefined, traceId: string | undefined = undefined) {
        super(message);
        this.name = 'SnapshotError';
        this.payload = payload;
        this.traceId = traceId;
    }
}

class SnapshotProtocolError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'SnapshotProtocolError';
    }
}

const createSnapshotId = (tabId: string): string => generateSecureId({ prefix: `snap_${tabId}`, format: 'hex', separator: '_' });
const MAX_RETIRED_SNAPSHOTS = 512;

const isFiniteTimestamp = <T>(value: T): value is T & number => typeof value === 'number' && Number.isFinite(value);

type SnapshotLogger = (level: 'debug' | 'warn' | 'error', message: string) => void;

const resolveSnapshotTimeout = (options: SnapshotRequestOptions | undefined): number => {
    const configured = options?.timeoutMs;
    return typeof configured === 'number' && Number.isFinite(configured) && configured > 0 ? configured : SNAPSHOT_TIMEOUT_MS;
};

class WebSocketSnapshotManager {
    #pendingSnapshots: Map<string, PendingSnapshot> = new Map();
    #retiredSnapshots: Map<string, number> = new Map();
    #logger: SnapshotLogger;

    constructor(logger: SnapshotLogger) {
        this.#logger = logger;
    }

    requestSnapshot(resourceName: string, tabId: string, parameters: JsonObject | null, sendRequest: (payload: JsonObject) => void, options: SnapshotRequestOptions = {}): Promise<SnapshotResponseEnvelope> {
        if (options.signal?.aborted) {
            return Promise.reject(createAbortError());
        }
        const snapshotId = createSnapshotId(tabId);
        const timeoutMs = resolveSnapshotTimeout(options);

        return new Promise<SnapshotResponseEnvelope>((resolve, reject) => {
            const timeout = setTimeout(() => {
                rejectPending(new Error(`${SNAPSHOT_TIMEOUT_MESSAGE_PREFIX} ${resourceName}`));
            }, timeoutMs);
            const pendingEntry: PendingSnapshot = {
                resolve,
                reject,
                timeout,
                removeAbortListener: null,
                resource: resourceName,
                settled: false
            };
            const cleanupPending = (retire: boolean): void => {
                clearTimeout(pendingEntry.timeout);
                if (pendingEntry.removeAbortListener !== null) {
                    pendingEntry.removeAbortListener();
                    pendingEntry.removeAbortListener = null;
                }
                this.#pendingSnapshots.delete(snapshotId);
                if (retire) this.#retireSnapshot(snapshotId, Math.max(timeoutMs, SNAPSHOT_TIMEOUT_MS * 2));
            };
            const rejectPending = (error: Error): void => {
                if (pendingEntry.settled) return;
                pendingEntry.settled = true;
                cleanupPending(true);
                reject(error);
            };

            if (options.signal) {
                const onAbort = (): void => {
                    rejectPending(createAbortError());
                };
                options.signal.addEventListener('abort', onAbort, { once: true });
                pendingEntry.removeAbortListener = () => options.signal?.removeEventListener('abort', onAbort);
            }

            this.#pendingSnapshots.set(snapshotId, pendingEntry);

            try {
                const payload = serializeSnapshotRequest(parameters || {}, resourceName, tabId, snapshotId);
                sendRequest(payload);
            } catch (error) {
                rejectPending(ensureError(error));
            }
        });
    }

    resolveSnapshot(data: WebSocketMessageData, isError: boolean): void {
        this.#pruneRetiredSnapshots();
        const snapshotId = resolveSnapshotId(data);
        if (!snapshotId) {
            throw new SnapshotProtocolError('Snapshot response missing snapshot_id');
        }

        const pending = this.#pendingSnapshots.get(snapshotId);
        if (!pending) {
            if (this.#retiredSnapshots.has(snapshotId)) {
                this.#logger('debug', `Ignored retired snapshot response: ${snapshotId}`);
                return;
            }
            throw new SnapshotProtocolError(`Received snapshot response for unknown request: ${snapshotId}`);
        }

        if (data.resource !== pending.resource) {
            this.#settlePendingSnapshot(snapshotId, pending);
            const receivedResource = data.resource ?? 'missing';
            this.#logger('error', `Snapshot resource mismatch for ${pending.resource}: ${receivedResource}`);
            pending.reject(new SnapshotError(`Snapshot response resource mismatch for ${pending.resource}`, data.raw));
            return;
        }

        this.#settlePendingSnapshot(snapshotId, pending);

        if (isError) {
            const message = resolveSnapshotErrorMessage(data);
            this.#logger('error', `Snapshot error for ${pending.resource}: ${message}`);
            const payload = data.error;
            const traceId = resolveSnapshotTraceId(data);
            pending.reject(new SnapshotError(message, payload, traceId));
            return;
        }

        this.#logger('debug', `Snapshot received for ${pending.resource}`);
        pending.resolve({
            resource: data.resource,
            data: data.data ?? null,
            timestampMs: isFiniteTimestamp(data.timestampMs) ? data.timestampMs : null
        });
    }

    #settlePendingSnapshot(snapshotId: string, pending: PendingSnapshot): void {
        pending.settled = true;
        this.#pendingSnapshots.delete(snapshotId);
        clearTimeout(pending.timeout);
        if (pending.removeAbortListener !== null) {
            pending.removeAbortListener();
            pending.removeAbortListener = null;
        }
        this.#retireSnapshot(snapshotId, SNAPSHOT_TIMEOUT_MS * 2);
    }

    rejectPendingSnapshots(error: Error): void {
        this.#pruneRetiredSnapshots();
        for (const [snapshotId, pending] of this.#pendingSnapshots.entries()) {
            pending.settled = true;
            clearTimeout(pending.timeout);
            if (pending.removeAbortListener !== null) {
                pending.removeAbortListener();
                pending.removeAbortListener = null;
            }
            this.#retireSnapshot(snapshotId, SNAPSHOT_TIMEOUT_MS);
            pending.reject(error);
        }
        this.#pendingSnapshots.clear();
    }

    #pruneRetiredSnapshots(): void {
        const now = Date.now();
        for (const [snapshotId, retirementDeadline] of this.#retiredSnapshots.entries()) {
            if (retirementDeadline <= now) this.#retiredSnapshots.delete(snapshotId);
        }
    }

    #retireSnapshot(snapshotId: string, retentionMs: number): void {
        this.#pruneRetiredSnapshots();
        while (this.#retiredSnapshots.size >= MAX_RETIRED_SNAPSHOTS) {
            const oldestSnapshotId = this.#retiredSnapshots.keys().next().value;
            if (typeof oldestSnapshotId !== 'string') break;
            this.#retiredSnapshots.delete(oldestSnapshotId);
        }
        this.#retiredSnapshots.set(snapshotId, Date.now() + Math.max(SNAPSHOT_TIMEOUT_MS, retentionMs));
    }
}

export { SnapshotError, SnapshotProtocolError, WebSocketSnapshotManager };
