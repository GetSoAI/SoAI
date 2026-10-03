/* SoAI - Variant probe result text mapping [frontend/assets/ts/features/models/variantprobe/variantresulttext/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveVariantFilterTokens } from '@features/models/variantprobe/variantfiltering/service.ts';

interface VariantResultTextInput {
    allCount: number;
    visibleCount: number;
    filterEnabled: boolean;
    query: string;
}

const hasVariantFilterQuery = (query: string): boolean => {
    return resolveVariantFilterTokens(query).length > 0;
};

const resolveVariantEmptyMessage = (input: VariantResultTextInput): string => {
    if (input.allCount === 0) {
        return i18n.t('models.modal.addModel.variantCheck.noVariants');
    }
    return input.filterEnabled && hasVariantFilterQuery(input.query) ? i18n.t('models.modal.addModel.variantSearchEmpty') : i18n.t('models.modal.addModel.variantCheck.noVariants');
};

const resolveVariantFilterStatusText = (input: VariantResultTextInput): string => {
    if (input.allCount === 0 || !input.filterEnabled || !hasVariantFilterQuery(input.query)) {
        return '';
    }
    return i18n.t('models.modal.addModel.variantSearchCount', { count: input.visibleCount, total: input.allCount });
};

export { resolveVariantEmptyMessage, resolveVariantFilterStatusText };
