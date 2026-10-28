/* SoAI - Localized backend variant compatibility guidance [frontend/assets/ts/core/plugins/backendVariantGuidance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveBackendCompatibilityMessage } from '@core/errors/operationCausePresentation.ts';

const resolveBackendVariantGuidance = (payload: BackendVariantsResponse): string | null => {
    if (payload.selectedVariantId === 'auto') {
        const excluded = payload.options.filter((option) => option.selectable && option.compatibility?.status === 'incompatible');
        const messages: string[] = [];
        if (excluded.length) messages.push(i18n.t('plugins.modal.backendVariants.autoCompatibility', { variants: excluded.map((option) => option.label).join(', ') }));
        if (payload.options.some((option) => option.selectable && option.compatibility?.status === 'unknown')) messages.push(i18n.t('plugins.modal.backendVariants.compatibilityUnknown'));
        return messages.length ? messages.join(' ') : null;
    }
    const selected = payload.options.find((option) => option.id === payload.selectedVariantId);
    if (selected?.compatibility?.status === 'incompatible') return resolveBackendCompatibilityMessage(selected.compatibility.reasons);
    if (selected?.compatibility?.status === 'unknown') return i18n.t('plugins.modal.backendVariants.compatibilityUnknown');
    return null;
};

export { resolveBackendVariantGuidance };
