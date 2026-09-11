/* SoAI - Frontend backend variant options [frontend/assets/ts/features/plugins/modals/backend/backendVariantOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';

interface BackendVariantOption {
    id: string;
    label: string;
    description: string;
    unavailableReason: string;
    selectable: boolean;
}

const AUTO_BACKEND_VARIANT_ID = 'auto';

const normalizeBackendVariantOptions = (payload: BackendVariantsResponse): { selected: string; installed: string | null; installedLabel: string | null; options: BackendVariantOption[] } => {
    const options = payload.options.map((item) => ({
        id: item.id,
        label: item.label,
        description: item.description ?? '',
        unavailableReason: item.unavailableReason ?? '',
        selectable: item.selectable
    }));
    if (!options.some((option) => option.id === AUTO_BACKEND_VARIANT_ID)) throw new Error('Backend variant response did not include the auto option');
    const installedOption = payload.installedVariantId === null ? undefined : options.find((option) => option.id === payload.installedVariantId);
    return { selected: payload.selectedVariantId, installed: installedOption?.id ?? null, installedLabel: installedOption?.label ?? null, options };
};

export { normalizeBackendVariantOptions };
export type { BackendVariantOption };
