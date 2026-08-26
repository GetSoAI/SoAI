/* SoAI - About page contracts [frontend/assets/ts/pages/about/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export interface AboutSystemInfo {
    version?: string | undefined;
}

export interface AboutHardwareCapabilities {
    platform?: string | undefined;
}

export interface AboutUiRefs {
    root: HTMLElement;
    logo: HTMLElement;
    version: HTMLElement;
    platform: HTMLElement;
}
