/* SoAI - Frontend application stages contracts [frontend/assets/ts/app/bootstrap/stages/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ThemePreference = 'auto' | 'light' | 'dark';
type Theme = 'light' | 'dark';

type BootstrapPhase = 'prime' | 'core' | 'feature';

interface BootstrapApi {
    applyTheme: () => Theme;
    start: () => BootstrapApi;
    getPhase: () => BootstrapPhase;
}

export type { BootstrapApi, BootstrapPhase, Theme, ThemePreference };
