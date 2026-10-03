/* SoAI - Shared model actions variant input [frontend/assets/ts/core/modelactions/variantInput.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { toTrimmedString } from '@core/normalize.ts';

interface ModelVariantInputParts {
    modelId: string;
    variantToken: string;
    canInlineVariant: boolean;
}

const canInlineModelVariantToken = (token: string): boolean => !token.includes('/') && !token.includes('\\');

const splitModelVariantInput = (value: string): ModelVariantInputParts => {
    const raw = toTrimmedString(value);
    if (!raw) {
        return { modelId: '', variantToken: '', canInlineVariant: false };
    }
    if (!raw.includes(':')) {
        return { modelId: raw, variantToken: '', canInlineVariant: true };
    }
    const [base, ...rest] = raw.split(':');
    const suffix = toTrimmedString(rest.join(':'));
    if (!suffix) {
        return { modelId: raw, variantToken: '', canInlineVariant: true };
    }
    if (raw.includes('://') || !canInlineModelVariantToken(suffix)) {
        return { modelId: raw, variantToken: '', canInlineVariant: false };
    }
    return {
        modelId: toTrimmedString(base) || base || raw,
        variantToken: suffix,
        canInlineVariant: true
    };
};

const VARIANT_REFERENCE_SEPARATOR = '@';

const readModelVariantRepository = (variant: Pick<ModelVariantResponse, 'id'>): string => {
    const id = toTrimmedString(variant.id);
    const separator = id.indexOf(VARIANT_REFERENCE_SEPARATOR);
    return separator < 0 ? '' : toTrimmedString(id.slice(0, separator));
};

const readModelVariantDownloadReference = (variant: Pick<ModelVariantResponse, 'id' | 'name' | 'normalizedName' | 'quantization'>): string => {
    const id = toTrimmedString(variant.id);
    const separator = id.indexOf(VARIANT_REFERENCE_SEPARATOR);
    const reference = separator < 0 ? '' : toTrimmedString(id.slice(separator + 1));
    return reference || toTrimmedString(variant.name) || toTrimmedString(variant.normalizedName) || toTrimmedString(variant.quantization);
};

export { canInlineModelVariantToken, readModelVariantDownloadReference, readModelVariantRepository, splitModelVariantInput };
export type { ModelVariantInputParts };
