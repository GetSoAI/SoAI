/* SoAI - Shared SoAIBench publication interaction flow [frontend/assets/ts/features/hardware/soaibenchPublicationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchPublicationReceipt } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { readApiRetryAfterSeconds } from '@core/api/errorPayloads.ts';
import { APIError, isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { securityApi } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface SoAIBenchPublicationRun {
    runId: string;
    publicationEligible: boolean;
    overallScore: number | null;
    measuredPasses: number | null;
}

interface SoAIBenchPublicationConfirmation {
    title: string;
    message: string;
    description: string;
    descriptionAllowHTML: boolean;
    confirmText: string;
    cancelText: string;
    variant: string;
    icon: string;
    confirmVariant: string;
    onConfirm: () => Promise<boolean>;
}

interface SoAIBenchPublicationFlowDependencies {
    preview(runId: string): Promise<string>;
    showResult(receipt: GpuSoAIBenchPublicationReceipt, message: string): Promise<void>;
    publish(runId: string): Promise<GpuSoAIBenchPublicationReceipt>;
    confirm(options: SoAIBenchPublicationConfirmation): Promise<boolean>;
    showNotification(message: string, type: NotificationType): void;
}

type PublicationControl = (disabled: boolean) => void;
type PublicationAttemptResult = { status: 'published'; receipt: GpuSoAIBenchPublicationReceipt } | { status: 'failed' };

class SoAIBenchPublicationFlow {
    readonly #dependencies: SoAIBenchPublicationFlowDependencies;
    readonly #inFlight = new Map<string, { controls: Set<PublicationControl>; promise: Promise<void> }>();

    constructor(dependencies: SoAIBenchPublicationFlowDependencies) {
        this.#dependencies = dependencies;
    }

    publish(run: SoAIBenchPublicationRun, control: PublicationControl): Promise<void> {
        if (!run.publicationEligible) throw new Error('SoAIBench run is not eligible for publication');
        const active = this.#inFlight.get(run.runId);
        if (active) {
            active.controls.add(control);
            control(true);
            return active.promise;
        }
        const controls = new Set([control]);
        const promise = this.#execute(run, controls).finally(() => {
            this.#inFlight.delete(run.runId);
            for (const setDisabled of controls) setDisabled(false);
        });
        this.#inFlight.set(run.runId, { controls, promise });
        return promise;
    }

    async #execute(run: SoAIBenchPublicationRun, controls: Set<PublicationControl>): Promise<void> {
        const score = run.overallScore;
        const passes = run.measuredPasses;
        if (score === null || passes !== 5) throw new Error('Publishable SoAIBench run evidence is incomplete');
        for (const setDisabled of controls) setDisabled(true);
        let receipt: GpuSoAIBenchPublicationReceipt | null = null;
        try {
            const preview = await this.#dependencies.preview(run.runId);
            const submission: { attempt: Promise<PublicationAttemptResult> | null } = { attempt: null };
            await this.#dependencies.confirm({
                title: i18n.t('hardware.soaibenchPublication.confirm.title'),
                message: i18n.t('hardware.soaibenchPublication.confirm.message', { score, passes }),
                description: `<p>${securityApi.escapeHtml(i18n.t('hardware.soaibenchPublication.confirm.description'))}</p><pre class="soaibench-publication-preview">${securityApi.escapeHtml(preview)}</pre>`,
                descriptionAllowHTML: true,
                confirmText: i18n.t('hardware.soaibenchPublication.action'),
                cancelText: i18n.t('common.cancel'),
                variant: 'info',
                icon: 'soaibench-gauge',
                confirmVariant: 'ui-variant-violet',
                onConfirm: async () => {
                    submission.attempt = (async (): Promise<PublicationAttemptResult> => {
                        let outcome: PublicationAttemptResult;
                        try {
                            const publishedReceipt = await this.#dependencies.publish(run.runId);
                            outcome = { status: 'published', receipt: publishedReceipt };
                        } catch (error) {
                            this.#dependencies.showNotification(this.#failureMessage(ensureError(error)), 'error');
                            outcome = { status: 'failed' };
                        }
                        return outcome;
                    })();
                    return (await submission.attempt).status === 'published';
                }
            });
            const attempt = submission.attempt;
            if (attempt === null) return;
            const outcome = await attempt;
            if (outcome.status === 'published') receipt = outcome.receipt;
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#dependencies.showNotification(this.#failureMessage(runtimeError), 'error');
        }
        if (receipt !== null) await this.#dependencies.showResult(receipt, this.#successMessage(receipt));
    }

    #successMessage(receipt: GpuSoAIBenchPublicationReceipt): string {
        if (receipt.state === 'published') return i18n.t('hardware.soaibenchPublication.outcomes.published');
        if (receipt.state === 'held_for_review') return i18n.t('hardware.soaibenchPublication.outcomes.heldForReview');
        return i18n.t('hardware.soaibenchPublication.outcomes.alreadyPublished');
    }

    #failureMessage(error: Error): string {
        if (error instanceof TypeError) return i18n.t('hardware.soaibenchPublication.outcomes.invalidResponse');
        if (isRequestTimeoutError(error)) return i18n.t('hardware.soaibenchPublication.outcomes.timeout');
        if (isNetworkError(error)) return i18n.t('hardware.soaibenchPublication.outcomes.offline');
        if (!(error instanceof APIError)) return i18n.t('hardware.soaibenchPublication.outcomes.unavailable');
        const code = error.reason || error.code || '';
        switch (code) {
            case 'soaibench_publication_offline':
                return i18n.t('hardware.soaibenchPublication.outcomes.offline');
            case 'soaibench_publication_timeout':
                return i18n.t('hardware.soaibenchPublication.outcomes.timeout');
            case 'soaibench_publication_rate_limited':
                return this.#withRetryDelay(i18n.t('hardware.soaibenchPublication.outcomes.rateLimited'), error);
            case 'soaibench_publication_capacity':
                return this.#withRetryDelay(i18n.t('hardware.soaibenchPublication.outcomes.capacity'), error);
            case 'soaibench_publication_rejected':
                return i18n.t('hardware.soaibenchPublication.outcomes.rejected');
            case 'soaibench_publication_conflict':
                return i18n.t('hardware.soaibenchPublication.outcomes.conflict');
            case 'soaibench_publication_invalid_response':
                return i18n.t('hardware.soaibenchPublication.outcomes.invalidResponse');
            default:
                return i18n.t('hardware.soaibenchPublication.outcomes.unavailable');
        }
    }

    #withRetryDelay(message: string, error: APIError): string {
        const retryAfter = readApiRetryAfterSeconds(error);
        if (retryAfter === null || !Number.isFinite(retryAfter) || retryAfter <= 0) return message;
        const seconds = Math.min(3600, Math.ceil(retryAfter));
        return `${message} ${i18n.t('hardware.soaibenchPublication.outcomes.retryAfter', { seconds })}`;
    }
}

export { SoAIBenchPublicationFlow };
export type { SoAIBenchPublicationFlowDependencies, SoAIBenchPublicationRun };
