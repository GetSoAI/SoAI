/* SoAI - Shared license service constants [frontend/assets/ts/core/licenseservice/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TextModalConfig, TextModalKey } from '@core/licenseservice/types.ts';

const TEXT_MODAL_KEYS: readonly TextModalKey[] = ['license', 'credits'];

const TEXT_MODAL_CONFIGS: Readonly<Record<TextModalKey, TextModalConfig>> = Object.freeze({
    license: {
        id: 'system-license-modal',
        key: 'license',
        className: 'system-license-modal'
    },
    credits: {
        id: 'system-credits-modal',
        key: 'credits',
        className: 'system-license-modal system-credits-modal'
    }
});

export { TEXT_MODAL_CONFIGS, TEXT_MODAL_KEYS };
