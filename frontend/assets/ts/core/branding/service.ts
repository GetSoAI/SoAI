/* SoAI - Shared branding service [frontend/assets/ts/core/branding/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BRAND_VARIANTS, LOGO_TYPES } from '@core/branding/constants.ts';
import type { BrandingDescriptor, BrandVariant, LogoConfig, LogoType, Theme } from '@core/branding/types.ts';
import { resolveAssetPath } from '@core/assetPaths.ts';
import type { DomApi } from '@core/dom/actions/types.ts';
import { errorHandler } from '@core/errorHandler.ts';

const resolveBrandVariantOverride = (variant: string | null): BrandVariant | null => {
    if (variant === null || variant === '') {
        return null;
    }
    if (variant === 'standard' || variant === 'product') {
        return variant;
    }
    throw new Error(`Branding received invalid variant: ${variant}`);
};

const resolveBrandTheme = (theme: string | undefined, getCurrentTheme: () => Theme): Theme => {
    if (theme === undefined) {
        return getCurrentTheme();
    }
    if (theme === 'dark' || theme === 'light') {
        return theme;
    }
    throw new Error(`Branding received invalid theme: ${theme}`);
};

const resolveBrandLogoType = (logoType: string): LogoType => {
    if (logoType === 'small' || logoType === 'ui') {
        return logoType;
    }
    throw new Error(`Branding received invalid logo type: ${logoType}`);
};

const resolveBrandVariant = (descriptor: BrandingDescriptor, variant: BrandVariant | null = null): BrandVariant => {
    return variant ?? descriptor.defaultVariant;
};

const resolveBrandVariantLogoConfig = (descriptor: BrandingDescriptor, logoType: LogoType, variant: BrandVariant): LogoConfig => {
    return descriptor.logos[variant][logoType];
};

const buildBrandPreloadedKey = (variant: BrandVariant, logoType: LogoType, theme: Theme): string => {
    return `${variant}_${logoType}_${theme}`;
};

const preloadBrandImage = (source: string): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
        const resolvedSource = resolveAssetPath(source);
        if (!resolvedSource) {
            reject(new Error(`Branding logo path resolution failed: ${source}`));
            return;
        }
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = resolvedSource;
    });
};

const preloadBrandLogos = async (descriptor: BrandingDescriptor, preloadedImages: Record<string, HTMLImageElement>): Promise<void> => {
    const tasks: Promise<void>[] = [];
    const pushTask = (variant: BrandVariant, logoType: LogoType, theme: Theme, source: string): void => {
        tasks.push(
            preloadBrandImage(source)
                .then((image) => {
                    preloadedImages[buildBrandPreloadedKey(variant, logoType, theme)] = image;
                })
                .catch((error) => {
                    errorHandler.debug('Branding', `Failed to preload logo: ${source}`, error);
                })
        );
    };

    for (const variant of BRAND_VARIANTS) {
        for (const logoType of LOGO_TYPES) {
            const config = resolveBrandVariantLogoConfig(descriptor, logoType, variant);
            pushTask(variant, logoType, 'dark', config.dark);
            pushTask(variant, logoType, 'light', config.light);
        }
    }

    await Promise.allSettled(tasks);
};

const waitForBrandImageLoaded = (image: HTMLImageElement, timeout: number): Promise<void> => {
    return new Promise((resolve) => {
        if (image.complete) {
            resolve();
            return;
        }

        let settled = false;
        const complete = (): void => {
            if (settled) {
                return;
            }
            settled = true;
            image.removeEventListener('load', complete);
            image.removeEventListener('error', complete);
            resolve();
        };
        image.addEventListener('load', complete);
        image.addEventListener('error', complete);
        setTimeout(complete, timeout);
    });
};

const detectCurrentBrandTheme = (domApi: DomApi): Theme => {
    const documentElement = domApi.getDocumentElement();
    if (domApi.hasClass(documentElement, 'theme-light')) return 'light';
    if (domApi.hasClass(documentElement, 'theme-dark')) return 'dark';
    if (domApi.hasClass(domApi.getBody(), 'theme-light')) return 'light';
    return 'dark';
};

const resolveBrandLogoPath = (descriptor: BrandingDescriptor, type: string, theme: string | undefined, variant: BrandVariant | null, getCurrentTheme: () => Theme): string => {
    const resolvedType = resolveBrandLogoType(type);
    const currentTheme = resolveBrandTheme(theme, getCurrentTheme);
    const resolvedVariant = resolveBrandVariant(descriptor, variant);
    const config = resolveBrandVariantLogoConfig(descriptor, resolvedType, resolvedVariant);
    const rawPath = currentTheme === 'light' ? config.light : config.dark;
    const resolved = resolveAssetPath(rawPath);
    if (!resolved) {
        throw new Error(`Branding logo path resolution failed: ${rawPath}`);
    }
    return resolved;
};

export { buildBrandPreloadedKey, detectCurrentBrandTheme, preloadBrandLogos, resolveBrandLogoPath, resolveBrandLogoType, resolveBrandTheme, resolveBrandVariant, resolveBrandVariantLogoConfig, resolveBrandVariantOverride, waitForBrandImageLoaded };
