/* SoAI - Licensing operation lifecycle classification [frontend/assets/ts/core/licensing/operationLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LicensingOperationIdentity {
    operationType: string;
    state: string;
}

const TERMINAL_LICENSING_OPERATION_STATES: ReadonlySet<string> = new Set(['succeeded', 'failed', 'cancelled']);

const isLicensingOperationInProgress = (state: string): boolean => {
    return !TERMINAL_LICENSING_OPERATION_STATES.has(state);
};

const canReconcileLicensingOperation = (operation: LicensingOperationIdentity | null): boolean => {
    return operation?.state === 'outcome_unknown';
};

export { canReconcileLicensingOperation, isLicensingOperationInProgress };
