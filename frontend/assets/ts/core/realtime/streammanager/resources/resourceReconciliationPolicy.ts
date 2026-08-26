/* SoAI - Validated resource reconciliation policy [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ReconciliationPolicy } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

const DEFAULT_RECONCILIATION_POLICY: Readonly<ReconciliationPolicy> = Object.freeze({
    maximumAttempts: 3,
    deadlineMs: 30_000,
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

export { DEFAULT_RECONCILIATION_POLICY, validateReconciliationPolicy };
