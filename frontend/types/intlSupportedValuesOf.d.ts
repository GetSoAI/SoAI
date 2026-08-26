/* SoAI - Intl supported-values type declarations [frontend/types/intlSupportedValuesOf.d.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

declare global {
    const Intl: typeof globalThis.Intl & {
        supportedValuesOf: (key: 'timeZone') => string[];
    };
}

export {};
