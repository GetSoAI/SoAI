/* SoAI - Wizard AI setup manual search view [frontend/assets/ts/pages/wizard/rendering/aisetup/search/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildModelSearchEmptyMarkup, buildModelSearchEntry, buildModelSearchErrorMarkup, buildModelSearchLoadingMarkup, buildVariantAdvisoryMarkup, buildVariantCheckEntry, buildVariantErrorMarkup, buildVariantLoadingMarkup, formatVariantDecimal } from '@features/models/public.ts';
import type { ModelSearchState } from '@pages/wizard/services/aisetup/AiSetupModelSearchController.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const AI_SEARCH_RESULT_ACTION = 'wizard-ai-search-result';
const AI_SEARCH_VARIANT_ACTION = 'wizard-ai-search-variant';

const renderAiSearchResults = (context: WizardViewContext, search: ModelSearchState): string => {
    if (search.status === 'idle') return '';
    if (search.status === 'loading') return buildModelSearchLoadingMarkup().html;
    if (search.status === 'error') return buildModelSearchErrorMarkup(search.error).html;
    if (search.results.length === 0) return buildModelSearchEmptyMarkup(getIconSync('search', { size: 32, strokeWidth: 1.5 })).html;
    return `<div class="model-search-results">${search.results.map((entry, index) => buildModelSearchEntry({ sanitizer: context.sanitizer, entry, index, action: AI_SEARCH_RESULT_ACTION })).join('')}</div>`;
};

const renderAiSearchVariants = (context: WizardViewContext, search: ModelSearchState): string => {
    if (search.variantStatus === 'idle') return '';
    if (search.variantStatus === 'loading') return buildVariantLoadingMarkup(i18n.t('models.modal.addModel.variantCheck.checking')).html;
    if (search.variantStatus === 'error') return buildVariantErrorMarkup(search.variantError).html;
    if (search.variants.length === 0) return buildVariantAdvisoryMarkup(i18n.t('models.modal.addModel.variantCheck.noVariants')).html;
    const renderContext = { host: { getIconSync }, sanitizer: context.sanitizer, selectedIndex: null, action: AI_SEARCH_VARIANT_ACTION, formatDecimal: formatVariantDecimal };
    return `<div class="variant-check-results">${search.variants.map((variant, index) => buildVariantCheckEntry(variant, index, renderContext)).join('')}</div>`;
};

export { AI_SEARCH_RESULT_ACTION, AI_SEARCH_VARIANT_ACTION, renderAiSearchResults, renderAiSearchVariants };
