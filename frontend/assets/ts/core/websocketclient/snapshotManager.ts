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

const createSnapshotIdNamespace = (): string => generateSecureId({ prefix: 'snap', format: 'hex', separator: '_' });
const createSnapshotId = (namespace: string, tabId: string): string => generateSecureId({ prefix: `${namespace}_${tabId}`, format: 'hex', separator: '_' });

const isFiniteTimestamp = <T>(value: T): value is T & number => typeof value === 'number' && Number.isFinite(value);

type SnapshotLogger = (level: 'debug' | 'warn' | 'error', message: string) => void;

const resolveSnapshotTimeout = (options: SnapshotRequestOptions | undefined): number => {
    const configured = options?.timeoutMs;
    return typeof configured === 'number' && Number.isFinite(configured) && configured > 0 ? configured : SNAPSHOT_TIMEOUT_MS;
};

class WebSocketSnapshotManager {
    #pendingSnapshots: Map<string, PendingSnapshot> = new Map();
    readonly #snapshotIdNamespace = createSnapshotIdNamespace();
    #logger: SnapshotLogger;

    constructor(logger: SnapshotLogger) {
        this.#logger = logger;
    }

    requestSnapshot(resourceName: string, tabId: string, parameters: JsonObject | null, sendRequest: (payload: JsonObject) => void, options: SnapshotRequestOptions = {}): Promise<SnapshotResponseEnvelope> {
        if (options.signal?.aborted) {
            return Promise.reject(createAbortError());
        }
        const snapshotId = createSnapshotId(this.#snapshotIdNamespace, tabId);
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
            const cleanupPending = (): void => {
                clearTimeout(pendingEntry.timeout);
                if (pendingEntry.removeAbortListener !== null) {
                    pendingEntry.removeAbortListener();
                    pendingEntry.removeAbortListener = null;
                }
                this.#pendingSnapshots.delete(snapshotId);
            };
            const rejectPending = (error: Error): void => {
                if (pendingEntry.settled) return;
                pendingEntry.settled = true;
                cleanupPending();
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
        const snapshotId = resolveSnapshotId(data);
        if (!snapshotId) {
            throw new SnapshotProtocolError('Snapshot response missing snapshot_id');
        }

        const pending = this.#pendingSnapshots.get(snapshotId);
        if (!pending) {
            if (snapshotId.startsWith(`${this.#snapshotIdNamespace}_`)) {
                this.#logger('debug', `Ignored settled snapshot response: ${snapshotId}`);
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
    }

    rejectPendingSnapshots(error: Error): void {
        for (const pending of this.#pendingSnapshots.values()) {
            pending.settled = true;
            clearTimeout(pending.timeout);
            if (pending.removeAbortListener !== null) {
                pending.removeAbortListener();
                pending.removeAbortListener = null;
            }
            pending.reject(error);
        }
        this.#pendingSnapshots.clear();
    }
}

export { SnapshotError, SnapshotProtocolError, WebSocketSnapshotManager };
