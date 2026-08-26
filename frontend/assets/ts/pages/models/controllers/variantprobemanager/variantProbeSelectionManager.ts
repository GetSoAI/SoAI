/* SoAI - Models page variant probe selection manager [frontend/assets/ts/pages/models/controllers/variantprobemanager/variantProbeSelectionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { splitModelVariantInput } from '@core/modelactions/variantInput.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { VariantProbeHost } from '@pages/models/controllers/variantprobemanager/types.ts';

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
    const tag = toTrimmedString(variant.name) || toTrimmedString(variant.normalizedName) || toTrimmedString(variant.quantization);
    context.host.setUIValue(context.requireInput('model-quant'), tag, { attribute: 'value' });

    const modelInput = context.requireInput('model-id');
    const current = readTrimmedInputValue(modelInput);
    const parsed = splitModelVariantInput(current);
    const baseModelId = parsed.canInlineVariant ? parsed.modelId : '';
    if (baseModelId && tag) {
        context.host.setUIValue(modelInput, `${baseModelId}:${tag}`, { attribute: 'value' });
    } else if (!current) {
        const variantId = toTrimmedString(variant.id);
        const extractedBase = variantId.includes('@') ? variantId.split('@')[0] : null;
        if (extractedBase && tag) {
            const extracted = splitModelVariantInput(extractedBase);
            const nextModelId = extracted.canInlineVariant ? `${extracted.modelId}:${tag}` : extracted.modelId;
            context.host.setUIValue(modelInput, nextModelId, { attribute: 'value' });
        }
    }
    return { selectedIndex: index, selectedVariant: variant };
};

const highlightVariantProbeSelection = (context: VariantProbeSelectionContext, selectedIndex: number | null): void => {
    const resultsElement = context.requireUiElement('model-variant-results');
    const entries = context.host.pageDom.query('.variant-check-entry', resultsElement);
    entries.forEach((entry) => {
        const entryIndex = optionalNonNegativeIntegerDataAttribute(entry, 'variant-index', 'Variant probe entry');
        context.host.pageDom.toggleClass(entry, 'variant-check-entry--selected', entryIndex === selectedIndex);
    });
};

export { highlightVariantProbeSelection, selectVariantProbeEntry };
export type { VariantProbeSelectionContext };
