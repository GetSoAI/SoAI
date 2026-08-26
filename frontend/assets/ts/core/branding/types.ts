/* SoAI - Shared branding contracts [frontend/assets/ts/core/branding/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type Theme = 'dark' | 'light';
type LogoType = 'small' | 'ui';
type BrandVariant = 'standard' | 'product';

interface LogoConfig {
    dark: string;
    light: string;
    aspectRatio: string;
}

type LogoTypes = Record<LogoType, LogoConfig>;

interface BrandingDescriptor {
    readonly defaultVariant: BrandVariant;
    readonly logos: Readonly<Record<BrandVariant, LogoTypes>>;
}

interface LogoInfo {
    currentPath: string | null;
    aspectRatio: string;
    preloaded: boolean;
}

interface BrandingInfo {
    currentTheme: Theme;
    logos: Record<string, LogoInfo>;
    initialized: boolean;
}

export type { BrandVariant, BrandingDescriptor, BrandingInfo, LogoConfig, LogoInfo, LogoType, LogoTypes, Theme };
