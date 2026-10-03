/* SoAI - Wizard licensing documents, status requests, and operation polling ownership [frontend/assets/ts/pages/wizard/controllers/page/WizardLicensingRequestsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingLegalDocumentSet, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { isDetailedWizardStatus, type WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { WizardLicensingDocumentResponse } from '@core/api/contracts/wizardLicensingMutations.ts';
import { getApiClient } from '@core/api/service.ts';
import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { createAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import type { LicenseServiceInterface } from '@core/licenseservice/types.ts';
import { LicensingOperationPollController } from '@core/licensing/operationPollController.ts';

interface WizardLicensingRequestsOptions {
    licenseService: LicenseServiceInterface;
    onPolledStatus(status: WizardStatusResponse): void;
    onPollFailure(): void;
}

class WizardLicensingRequestsController {
    readonly #licenseService: LicenseServiceInterface;
    readonly #licenseLoad = new AsyncOnceGuard<string>();
    readonly #evaluationTermsLoad = new AsyncOnceGuard<WizardLicensingDocumentResponse>();
    readonly #purchaseTermsLoad = new AsyncOnceGuard<WizardLicensingDocumentResponse>();
    readonly #governingDocumentLoads = new Map<LicensingLegalFlow, AsyncOnceGuard<LicensingLegalDocumentSet>>();
    readonly #statusRequests = new LatestRequestController();
    readonly #licensingRequests = new LatestRequestController();
    readonly #poll: LicensingOperationPollController<WizardStatusResponse>;
    #pollFailureNotified = false;

    constructor(options: WizardLicensingRequestsOptions) {
        this.#licenseService = options.licenseService;
        this.#poll = new LicensingOperationPollController({
            fetchStatus: (signal) => this.#refreshStatusRequired(signal),
            onStatus: (status) => {
                this.#pollFailureNotified = false;
                options.onPolledStatus(status);
            },
            onFailure: () => {
                if (this.#pollFailureNotified) return;
                this.#pollFailureNotified = true;
                options.onPollFailure();
            }
        });
    }

    async fetchLicenseText(): Promise<string> {
        return this.#licenseLoad.run(async () => {
            const data = await this.#licenseService.fetchLicenseData();
            if (typeof data.licenseText !== 'string' || !data.licenseText.trim()) throw new Error('WizardPage: license text is unavailable');
            return data.licenseText;
        });
    }

    evaluationTerms(): Promise<WizardLicensingDocumentResponse> {
        return this.#evaluationTermsLoad.run(() => getApiClient().webui.wizard.evaluationTerms());
    }

    personalPurchaseTerms(): Promise<WizardLicensingDocumentResponse> {
        return this.#purchaseTermsLoad.run(() => getApiClient().webui.wizard.personalPurchaseTerms());
    }

    governingDocuments(flow: LicensingLegalFlow): Promise<LicensingLegalDocumentSet> {
        let load = this.#governingDocumentLoads.get(flow);
        if (load === undefined) {
            load = new AsyncOnceGuard<LicensingLegalDocumentSet>();
            this.#governingDocumentLoads.set(flow, load);
        }
        return load.run(() => getApiClient().webui.wizard.governingDocuments(flow));
    }

    observeStatus(status: WizardStatusResponse): void {
        this.#poll.update(status);
    }

    invalidateStatusObservation(): void {
        this.#poll.pause();
        this.#statusRequests.invalidate();
    }

    invalidateLicensingRequests(): void {
        this.#licensingRequests.invalidate();
    }

    async mutateStatus(operation: (signal: AbortSignal) => Promise<WizardStatusResponse>): Promise<WizardStatusResponse> {
        this.invalidateStatusObservation();
        return this.runLicensingRequest(operation);
    }

    async runLicensingRequest<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
        const result = await this.#licensingRequests.runLatest((run) => operation(run.signal));
        if (result === null) throw createAbortError('Wizard licensing request superseded');
        return result;
    }

    async refreshStatus(signal?: AbortSignal): Promise<WizardStatusResponse | null> {
        return this.#statusRequests.runLatest(async (run) =>
            runWithAbortSignalScope([run.signal, signal], async (combinedSignal) => {
                const status = await getApiClient().webui.wizard.status({ signal: combinedSignal });
                if (!isDetailedWizardStatus(status)) throw new Error('Wizard licensing details require an active setup ceremony');
                return status;
            })
        );
    }

    destroy(): void {
        this.#licenseLoad.dispose();
        this.#evaluationTermsLoad.dispose();
        this.#purchaseTermsLoad.dispose();
        for (const load of this.#governingDocumentLoads.values()) load.dispose();
        this.#governingDocumentLoads.clear();
        this.#statusRequests.invalidate();
        this.#licensingRequests.invalidate();
        this.#poll.destroy();
    }

    async #refreshStatusRequired(signal: AbortSignal): Promise<WizardStatusResponse> {
        const status = await this.refreshStatus(signal);
        if (status === null) throw createAbortError('Wizard licensing status refresh superseded');
        return status;
    }
}

export { WizardLicensingRequestsController };
