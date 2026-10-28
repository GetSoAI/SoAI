/* SoAI - Models feature variant probe selection manager [frontend/assets/ts/features/models/variantprobe/variantProbeSelectionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { canInlineModelVariantToken, readModelVariantDownloadReference, readModelVariantRepository, splitModelVariantInput } from '@core/modelactions/variantInput.ts';
import type { VariantProbeHost } from '@features/models/variantprobe/types.ts';

interface VariantProbeSelectionContext {
    host: VariantProbeHost;
    requireInput: (token: string) => HTMLInputElement;
    requireUiElement: (token: string) => Element;
    results: readonly ModelVariantResponse[];
}

interface VariantProbeSelectionState {
    selectedIndex: number;
    selectedVariant: ModelVariantResponse;
}

const selectVariantProbeEntry = (element: Element | null, context: VariantProbeSelectionContext): VariantProbeSelectionState | null => {
    if (!element) return null;
    const index = optionalNonNegativeIntegerDataAttribute(element, 'variant-index', 'Variant probe entry');
    if (index === null || index >= context.results.length) return null;

    const variant = context.results[index];
    if (!variant) return null;
    const tag = readModelVariantDownloadReference(variant);
    context.host.setUIValue(context.requireInput('model-quant'), tag, { attribute: 'value' });

    const withTag = (modelId: string): string => (tag && canInlineModelVariantToken(tag) ? `${modelId}:${tag}` : modelId);
    const modelInput = context.requireInput('model-id');
    const current = readTrimmedInputValue(modelInput);
    const parsed = splitModelVariantInput(current);
    const baseModelId = parsed.canInlineVariant ? parsed.modelId : '';
    if (baseModelId) {
        context.host.setUIValue(modelInput, withTag(baseModelId), { attribute: 'value' });
    } else if (!current) {
        const repository = splitModelVariantInput(readModelVariantRepository(variant));
        if (repository.modelId) context.host.setUIValue(modelInput, repository.canInlineVariant ? withTag(repository.modelId) : repository.modelId, { attribute: 'value' });
    }
    return { selectedIndex: index, selectedVariant: variant };
};

const highlightVariantProbeSelection = (resultsElement: Element, selectedIndex: number | null): void => {
    const entries = dom.resolveAll('.variant-check-entry', resultsElement);
    entries.forEach((entry) => {
        const entryIndex = optionalNonNegativeIntegerDataAttribute(entry, 'variant-index', 'Variant probe entry');
        const selected = entryIndex === selectedIndex;
        dom.toggleClass(entry, 'variant-check-entry--selected', selected);
        entry.setAttribute('aria-pressed', String(selected));
    });
};

export { highlightVariantProbeSelection, selectVariantProbeEntry };
export type { VariantProbeSelectionContext };
