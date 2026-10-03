/* SoAI - Wizard AI setup manual model search [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupModelSearchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { modelActions } from '@core/modelactions/public.ts';
import { readModelVariantDownloadReference, readModelVariantRepository } from '@core/modelactions/variantInput.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import { parseModelSearchResults, type ModelSearchResults } from '@features/models/public.ts';
import type { LocalModelPick } from '@pages/wizard/services/aisetup/state.ts';

const MODEL_SEARCH_LIMIT = 20;

type RequestStatus = 'idle' | 'loading' | 'ready' | 'error';

interface ModelSearchState {
    pluginName: string | null;
    query: string;
    status: RequestStatus;
    results: ModelSearchResults;
    error: string | null;
    repositoryId: string | null;
    variantStatus: RequestStatus;
    variants: ModelVariantResponse[];
    variantError: string | null;
}

const createModelSearchState = (): ModelSearchState => ({ pluginName: null, query: '', status: 'idle', results: [], error: null, repositoryId: null, variantStatus: 'idle', variants: [], variantError: null });

class AiSetupModelSearchController {
    readonly #onChange: () => void;
    readonly #searches = new LatestRequestController();
    readonly #probes = new LatestRequestController();
    state: ModelSearchState = createModelSearchState();

    constructor(onChange: () => void) {
        this.#onChange = onChange;
    }

    dispose(): void {
        this.#searches.invalidate();
        this.#probes.invalidate();
    }

    bindEngine(pluginName: string): void {
        if (this.state.pluginName === null || this.state.pluginName === pluginName) return;
        this.dispose();
        this.state = createModelSearchState();
        this.#onChange();
    }

    async search(pluginName: string, query: string): Promise<void> {
        const trimmed = query.trim();
        this.#probes.invalidate();
        this.state = { ...createModelSearchState(), pluginName: trimmed ? pluginName : null, query: trimmed, status: trimmed ? 'loading' : 'idle' };
        this.#onChange();
        if (!trimmed) {
            this.#searches.invalidate();
            return;
        }
        try {
            const results = await this.#searches.runLatest((run) => modelActions.searchRemoteModels(pluginName, trimmed, { limit: MODEL_SEARCH_LIMIT, signal: run.signal }));
            if (results === null) return;
            this.state = { ...this.state, status: 'ready', results: parseModelSearchResults(isJsonValue(results) ? results : undefined) };
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) return;
            errorHandler.warn('WizardAiSetup', 'Model search failed', runtimeError);
            this.state = { ...this.state, status: 'error', error: extractUserFacingErrorMessage(runtimeError) };
        }
        this.#onChange();
    }

    async selectResult(pluginName: string, index: number): Promise<void> {
        const repositoryId = toTrimmedString(this.state.results[index]?.id);
        if (!repositoryId || this.state.pluginName !== pluginName) return;
        this.state = { ...this.state, repositoryId, variantStatus: 'loading', variants: [], variantError: null };
        this.#onChange();
        try {
            const variants = await this.#probes.runLatest(() => modelActions.probeModelVariants(pluginName, repositoryId));
            if (variants === null) return;
            this.state = { ...this.state, variantStatus: 'ready', variants };
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) return;
            errorHandler.warn('WizardAiSetup', 'Model variant probe failed', runtimeError);
            this.state = { ...this.state, variantStatus: 'error', variantError: extractUserFacingErrorMessage(runtimeError) };
        }
        this.#onChange();
    }

    readVariantPick(pluginName: string, index: number): LocalModelPick | null {
        const variant = this.state.variants[index];
        const repositoryId = this.state.repositoryId;
        const artifactReference = variant === undefined ? '' : readModelVariantDownloadReference(variant);
        if (variant === undefined || repositoryId === null || !artifactReference || this.state.pluginName !== pluginName) return null;
        return { catalogId: null, pluginName, repositoryId: readModelVariantRepository(variant) || repositoryId, artifactReference, artifactName: toTrimmedString(variant.name) || artifactReference };
    }
}

export { AiSetupModelSearchController };
export type { ModelSearchState };
