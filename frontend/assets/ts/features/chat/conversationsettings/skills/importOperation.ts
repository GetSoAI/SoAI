/* SoAI - Owner-bound skill upload identity and uncertain outcome reconciliation [frontend/assets/ts/features/chat/conversationsettings/skills/importOperation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiSkillEndpoints } from '@core/api/endpoints/webuiSkillEndpoints.ts';
import type { SkillBatchImportReceipt } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { APIError, isNonRetryableApiRequestError } from '@core/apiError.ts';
import { readApiErrorDetail, readApiRetryAfterSeconds } from '@core/api/errorPayloads.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { monotonicMs } from '@core/time/clock.ts';

interface PendingSkillImport {
    readonly file: File;
    readonly uploadId: string;
    readonly ownerId: number;
    attempted: boolean;
    unresolvedFailure: Error | null;
    retryAfterMs: number;
}

class SkillImportOperation {
    readonly #api: WebuiSkillEndpoints;
    readonly #currentOwner: () => number | null;
    readonly #generation = new SequenceToken();
    #pending: PendingSkillImport | null = null;
    #busy: number | null = null;

    constructor(api: WebuiSkillEndpoints, currentOwner: () => number | null) {
        this.#api = api;
        this.#currentOwner = currentOwner;
    }

    get pending(): boolean {
        return this.#pending !== null;
    }
    get busy(): boolean {
        return this.#busy !== null;
    }

    stage(file: File): void {
        if (this.busy) throw new Error('A skill upload is already in progress.');
        if (this.#pending?.attempted) throw new Error('Reconcile the pending skill import before selecting another file.');
        const ownerId = this.#currentOwner();
        if (ownerId === null) throw createAbortError('Skill upload owner is unavailable.');
        this.#generation.next();
        this.#pending = { file, uploadId: generateSecureId(), ownerId, attempted: false, unresolvedFailure: null, retryAfterMs: 0 };
    }

    discardOwner(): void {
        this.#generation.invalidate();
        this.#pending = null;
        this.#busy = null;
    }

    async run(): Promise<SkillBatchImportReceipt | null> {
        const pending = this.#pending;
        if (pending === null || this.busy) return null;
        const generation = this.#generation.value;
        this.#requireOwner(pending, generation);
        this.#busy = generation;
        try {
            if (pending.attempted) {
                const receipt = await this.#receipt(pending, generation);
                if (receipt !== null) return this.#accept(pending, generation, receipt);
                if (pending.unresolvedFailure !== null && (readApiErrorDetail(pending.unresolvedFailure, 'retry_guidance') === 'do_not_retry' || monotonicMs() < pending.retryAfterMs)) throw pending.unresolvedFailure;
            }
            this.#requireOwner(pending, generation);
            pending.attempted = true;
            try {
                const receipt = await this.#api.importBatch(pending.file, pending.uploadId);
                return this.#accept(pending, generation, receipt);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#requireOwner(pending, generation);
                if (isNonRetryableApiRequestError(runtimeError) || (runtimeError instanceof APIError && [409, 413, 415].includes(runtimeError.status))) {
                    this.#pending = null;
                    throw runtimeError;
                }
                pending.unresolvedFailure = runtimeError;
                pending.retryAfterMs = monotonicMs() + (readApiRetryAfterSeconds(runtimeError) ?? 0) * 1000;
                const receipt = await this.#receipt(pending, generation);
                if (receipt !== null) return this.#accept(pending, generation, receipt);
                throw runtimeError;
            }
        } finally {
            if (this.#busy === generation) this.#busy = null;
        }
    }

    async #receipt(pending: PendingSkillImport, generation: number): Promise<SkillBatchImportReceipt | null> {
        this.#requireOwner(pending, generation);
        try {
            const receipt = await this.#api.importBatchReceipt(pending.uploadId);
            this.#requireOwner(pending, generation);
            if (receipt.uploadId !== pending.uploadId) throw new TypeError('Skill receipt identity differs from its operation.');
            return receipt;
        } catch (error) {
            this.#requireOwner(pending, generation);
            if (error instanceof APIError && error.status === 404) return null;
            throw error;
        }
    }

    #accept(pending: PendingSkillImport, generation: number, receipt: SkillBatchImportReceipt): SkillBatchImportReceipt {
        this.#requireOwner(pending, generation);
        if (receipt.uploadId !== pending.uploadId) throw new TypeError('Skill receipt identity differs from its operation.');
        this.#pending = null;
        return receipt;
    }

    #requireOwner(pending: PendingSkillImport, generation: number): void {
        if (!this.#generation.isActive(generation) || this.#pending !== pending || this.#currentOwner() !== pending.ownerId) throw createAbortError('Skill upload owner changed.');
    }
}

export { SkillImportOperation };
