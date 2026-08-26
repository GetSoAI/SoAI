/* SoAI - Shared branding constants [frontend/assets/ts/core/branding/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BrandingDescriptor, BrandVariant, LogoTypes, LogoType } from '@core/branding/types.ts';

const STANDARD_LOGO_TYPES: LogoTypes = {
    small: {
        dark: 'img/soai/soai-logo-small-dark.png',
        light: 'img/soai/soai-logo-small-light.png',
        aspectRatio: '1:1'
    },
    ui: {
        dark: 'img/soai/soai-logo-dark.png',
        light: 'img/soai/soai-logo-light.png',
        aspectRatio: '17:40'
    }
};

const BASE_BRANDING: BrandingDescriptor = Object.freeze({
    defaultVariant: 'standard',
    logos: Object.freeze({
        standard: STANDARD_LOGO_TYPES,
        product: STANDARD_LOGO_TYPES
    })
});

const LOGO_TYPES: readonly LogoType[] = ['small', 'ui'];
const BRAND_VARIANTS: readonly BrandVariant[] = ['standard', 'product'];
const LOGO_TRANSITION_DURATION_MS = 300;

export { BASE_BRANDING, BRAND_VARIANTS, LOGO_TRANSITION_DURATION_MS, LOGO_TYPES, STANDARD_LOGO_TYPES };
