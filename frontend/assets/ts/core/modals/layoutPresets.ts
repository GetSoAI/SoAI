/* SoAI - Shared modals layout presets [frontend/assets/ts/core/modals/layoutPresets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalConfig, ModalLayoutPreset } from '@core/modals/types.ts';

type ModalLayoutContract = Readonly<Pick<ModalConfig, 'size' | 'minWidth' | 'minHeight'>>;

const MODAL_LAYOUT_PRESETS: Readonly<Record<ModalLayoutPreset, ModalLayoutContract>> = Object.freeze({
    md: Object.freeze({ size: 'md', minWidth: 650, minHeight: 450 }),
    lg: Object.freeze({ size: 'lg', minWidth: 760, minHeight: 540 }),
    xl: Object.freeze({ size: 'xl', minWidth: 900, minHeight: 650 })
});

const isModalLayoutPreset = <T>(value: T): value is T & ModalLayoutPreset => {
    return value === 'md' || value === 'lg' || value === 'xl';
};

const resolveModalLayoutContract = (value: ModalLayoutPreset): ModalLayoutContract => {
    if (!isModalLayoutPreset(value)) {
        throw new Error(`Modal layout preset must be "md", "lg", or "xl" (found "${String(value)}")`);
    }
    return MODAL_LAYOUT_PRESETS[value];
};

export { isModalLayoutPreset, resolveModalLayoutContract };
export type { ModalLayoutContract };
