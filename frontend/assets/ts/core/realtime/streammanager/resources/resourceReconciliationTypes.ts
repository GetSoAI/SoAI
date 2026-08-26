/* SoAI - Resource reconciliation state and ownership contracts [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Deferred } from '@core/runtime/deferred.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ReconciledResourceStatus = 'initializing' | 'unavailable' | 'ready' | 'recovering' | 'disconnected' | 'error';
type ResourceAttemptSource = 'fetch' | 'websocket-snapshot';

interface ReconciliationPolicy {
    maximumAttempts: number;
    deadlineMs: number;
    abortCleanupDeadlineMs: number;
    recoveryInitialDelayMs: number;
    recoveryMaximumDelayMs: number;
    recoveryResetAfterMs: number;
}

interface ResourceReconciliationSnapshot {
    name: string;
    value: JsonValue | null;
    status: ReconciledResourceStatus;
    revision: number;
    lifecycleGeneration: number;
    configurationRevision: number;
    desiredReconciliationRevision: number;
    committedReconciliationRevision: number;
    transportEpoch: number;
    receiveSequence: number;
    transitionType: string;
    authoritativeSource: string | null;
    authoritativeReason: string | null;
    authoritativeUpdatedAtMonotonicMs: number | null;
    staleSinceMonotonicMs: number | null;
    retained: boolean;
    maintenance: boolean;
    error: Error | null;
}

interface ResourceStateDeliveryContext {
    type: string;
    transitionType: string;
    initial: boolean;
}

interface ResourceAttemptContext {
    signal: AbortSignal;
    reconciliationRevision: number;
    transportEpoch: number;
}

type ResourceAttemptExecutor = (context: ResourceAttemptContext) => Promise<JsonValue>;
type ResourceReconciliationListener = (snapshot: ResourceReconciliationSnapshot) => void;
type ResourceStateListener = (snapshot: ResourceReconciliationSnapshot, context: ResourceStateDeliveryContext) => void;
type ResourceValueListener = (value: JsonValue | null, context: ResourceStateDeliveryContext) => void;

interface ResourceReconcileOptions {
    force?: boolean;
    signal?: AbortSignal;
    source?: ResourceAttemptSource;
}

interface PushCommitContext {
    transportEpoch: number;
    receiveSequence: number;
    remoteTimestampMs: number | null;
}

interface ResourceWaiter {
    targetReconciliationRevision: number;
    deferred: Deferred<JsonValue | null>;
    signal: AbortSignal | null;
    abortListener: (() => void) | null;
}

interface ResourceAttempt {
    identity: symbol;
    targetReconciliationRevision: number;
    transportEpoch: number;
    lifecycleGeneration: number;
    configurationRevision: number;
    source: ResourceAttemptSource;
    controller: AbortController;
    executor: ResourceAttemptExecutor;
    authoritative: boolean;
    cleanupTimer: number | null;
    promise: Promise<void>;
}

interface QueuedResourceAttempt {
    targetReconciliationRevision: number;
    source: ResourceAttemptSource;
    executor: ResourceAttemptExecutor;
}

export type { PushCommitContext, QueuedResourceAttempt, ReconciledResourceStatus, ReconciliationPolicy, ResourceAttempt, ResourceAttemptContext, ResourceAttemptExecutor, ResourceAttemptSource, ResourceReconcileOptions, ResourceReconciliationListener, ResourceReconciliationSnapshot, ResourceStateDeliveryContext, ResourceStateListener, ResourceValueListener, ResourceWaiter };
