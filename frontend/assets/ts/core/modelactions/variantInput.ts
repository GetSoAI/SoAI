/* SoAI - Shared model actions variant input [frontend/assets/ts/core/modelactions/variantInput.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

interface ModelVariantInputParts {
    modelId: string;
    variantToken: string;
    canInlineVariant: boolean;
}

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
    if (raw.includes('://') || suffix.includes('/') || suffix.includes('\\')) {
        return { modelId: raw, variantToken: '', canInlineVariant: false };
    }
    return {
        modelId: toTrimmedString(base) || base || raw,
        variantToken: suffix,
        canInlineVariant: true
    };
};

export { splitModelVariantInput };
export type { ModelVariantInputParts };
