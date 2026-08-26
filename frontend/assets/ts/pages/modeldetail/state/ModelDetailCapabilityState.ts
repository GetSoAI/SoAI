/* SoAI - Model detail OpenAI capability override state ownership [frontend/assets/ts/pages/modeldetail/state/ModelDetailCapabilityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireCatalogStore, resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor } from '@features/catalog/public.ts';
import { createOpenAICapabilityOverrideState, hasOpenAICapabilityOverrideChanges, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';

class ModelDetailCapabilityState {
    #state: OpenAICapabilityOverrideState | null = null;

    get(model: ModelRecord | null, modelId: string | null): OpenAICapabilityOverrideState | null {
        if (!model || !modelId) {
            this.#state = null;
            return null;
        }
        if (!this.#state || this.#state.modelId !== modelId) {
            this.#state = createOpenAICapabilityOverrideState(model, modelId);
        }
        return this.#state;
    }

    rehydrate(model: ModelRecord, modelId: string): OpenAICapabilityOverrideState {
        if (this.#state && this.#state.modelId === modelId && hasOpenAICapabilityOverrideChanges(this.#state)) {
            return this.#state;
        }
        this.#state = createOpenAICapabilityOverrideState(model, modelId);
        return this.#state;
    }

    reset(): void {
        this.#state = null;
    }

    resolveLabel(category: OpenAICapabilityOverrideCategory, token: string): string {
        requireCatalogStore();
        return category === 'modalities' ? resolveOpenAIModalityDescriptor(token).label : resolveOpenAITokenDescriptor(category, token).label;
    }
}

export { ModelDetailCapabilityState };
