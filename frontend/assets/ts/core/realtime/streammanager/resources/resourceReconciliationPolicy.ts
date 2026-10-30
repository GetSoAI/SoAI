/* SoAI - Validated resource reconciliation policy [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MEMORY_LIBRARY, CHAT_PRESETS } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceReconciliationSnapshot, ReconciliationPolicy } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

const isSubscriptionOwnedResource = (name: string): boolean => name === MEMORY_LIBRARY || name === CHAT_PRESETS;

const isResourceRecoveryBlocked = (snapshot: ResourceReconciliationSnapshot): boolean => snapshot.maintenance || snapshot.status === 'disconnected' || ['resource-interest-rejected', 'library-access-denied', 'library-protocol-invalid'].includes(snapshot.authoritativeReason ?? '');

const DEFAULT_RECONCILIATION_POLICY: Readonly<ReconciliationPolicy> = Object.freeze({
    maximumAttempts: 3,
    deadlineMs: 90_000,
    abortCleanupDeadlineMs: 5_000,
    recoveryInitialDelayMs: 500,
    recoveryMaximumDelayMs: 30_000,
    recoveryResetAfterMs: 60_000
});

const validateReconciliationPolicy = (policy: ReconciliationPolicy): ReconciliationPolicy => {
    if (!Number.isSafeInteger(policy.maximumAttempts) || policy.maximumAttempts < 1 || policy.maximumAttempts > 10) throw new Error('Reconciliation policy maximumAttempts is invalid');
    if (!Number.isFinite(policy.deadlineMs) || policy.deadlineMs < 100 || policy.deadlineMs > 120_000) throw new Error('Reconciliation policy deadlineMs is invalid');
    if (!Number.isFinite(policy.abortCleanupDeadlineMs) || policy.abortCleanupDeadlineMs < 100 || policy.abortCleanupDeadlineMs > 30_000) throw new Error('Reconciliation policy abortCleanupDeadlineMs is invalid');
    if (!Number.isFinite(policy.recoveryInitialDelayMs) || policy.recoveryInitialDelayMs < 1) throw new Error('Reconciliation policy recoveryInitialDelayMs is invalid');
    if (!Number.isFinite(policy.recoveryMaximumDelayMs) || policy.recoveryMaximumDelayMs < policy.recoveryInitialDelayMs || policy.recoveryMaximumDelayMs > 30_000) throw new Error('Reconciliation policy recoveryMaximumDelayMs is invalid');
    if (!Number.isFinite(policy.recoveryResetAfterMs) || policy.recoveryResetAfterMs < 1) throw new Error('Reconciliation policy recoveryResetAfterMs is invalid');
    return Object.freeze({ ...policy });
};

export { isSubscriptionOwnedResource, isResourceRecoveryBlocked, DEFAULT_RECONCILIATION_POLICY, validateReconciliationPolicy };
