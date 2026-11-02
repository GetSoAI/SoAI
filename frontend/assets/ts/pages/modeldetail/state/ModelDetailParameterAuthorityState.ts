/* SoAI - Model detail parameter snapshot authority state [frontend/assets/ts/pages/modeldetail/state/ModelDetailParameterAuthorityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { deepClone } from '@core/primitives/clone.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import type { ParametersData } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ParameterCategory, ParameterDefinition } from '@pages/modeldetail/contracts/parameterTypes.ts';

type ParameterAuthorityStatus = 'current' | 'refreshing' | 'stale' | 'unavailable';
type ParameterUnavailableReason = 'plugin_operation_in_progress' | 'plugin_unregistered' | 'refresh_failed';
type ParameterSnapshotOutcome = 'reconciled' | 'stale' | 'unavailable' | 'cancelled';

interface ParameterSchemaShape {
    definitions: Record<string, ParameterDefinition | null>;
    categories: Record<string, ParameterCategory>;
}

interface PendingParameterSnapshot {
    readonly token: number;
    readonly payload: ParametersData;
    readonly receivedAtMs: number;
    readonly schemaChanged: boolean;
}

const readParameterSchema = (payload: ParametersData): ParameterSchemaShape => ({
    definitions: Object.fromEntries(Object.entries(payload.parameters ?? {}).map(([key, parameter]) => [key, parameter.definition ?? null])),
    categories: payload.categories ?? {}
});

class ModelDetailParameterAuthority {
    readonly reads = new SequenceToken();
    status: ParameterAuthorityStatus = 'current';
    reason: ParameterUnavailableReason | null = null;
    validated = false;
    saving = false;
    displayedAtMs: number | null = null;
    pending: PendingParameterSnapshot | null = null;
    exhaustionNotified = false;
    recovery: Promise<ParameterSnapshotOutcome> | null = null;
    invalidationGeneration = 0;
    reconciliationExhausted = false;
    #appliedSchema: ParameterSchemaShape | null = null;

    get schemaBlocked(): boolean {
        return this.pending?.schemaChanged === true;
    }

    get canSubmit(): boolean {
        return this.validated && this.status !== 'unavailable' && !this.schemaBlocked;
    }

    invalidate(): void {
        this.reads.invalidate();
        this.invalidationGeneration += 1;
    }

    reset(): void {
        this.invalidate();
        this.reconciliationExhausted = false;
        this.status = 'current';
        this.reason = null;
        this.validated = false;
        this.saving = false;
        this.displayedAtMs = null;
        this.pending = null;
        this.exhaustionNotified = false;
        this.recovery = null;
        this.#appliedSchema = null;
    }

    recordApplied(payload: ParametersData, displayedAtMs: number | null, validated: boolean): void {
        this.#appliedSchema = deepClone(readParameterSchema(payload));
        this.displayedAtMs = displayedAtMs;
        this.validated = validated;
        this.pending = null;
    }

    matchesAppliedSchema(payload: ParametersData): boolean {
        return this.#appliedSchema !== null && deepEqual(this.#appliedSchema, readParameterSchema(payload));
    }

    holdPending(token: number, payload: ParametersData, receivedAtMs: number): void {
        const schemaChanged = this.#appliedSchema !== null && !this.matchesAppliedSchema(payload);
        this.pending = { token, payload, receivedAtMs, schemaChanged };
    }
}

export { ModelDetailParameterAuthority };
export type { ParameterAuthorityStatus, ParameterUnavailableReason, ParameterSnapshotOutcome, PendingParameterSnapshot };
