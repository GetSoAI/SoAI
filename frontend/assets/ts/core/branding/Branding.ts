/* SoAI - Frontend branding service ownership [frontend/assets/ts/core/branding/Branding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LOGO_TRANSITION_DURATION_MS, LOGO_TYPES } from '@core/branding/constants.ts';
import { buildBrandPreloadedKey, detectCurrentBrandTheme, preloadBrandLogos, resolveBrandLogoPath, resolveBrandLogoType, resolveBrandTheme, resolveBrandVariant, resolveBrandVariantLogoConfig, resolveBrandVariantOverride, waitForBrandImageLoaded } from '@core/branding/service.ts';
import type { BrandingDescriptor, BrandingInfo, BrandVariant, LogoInfo, Theme } from '@core/branding/types.ts';
import { resolveAssetPath } from '@core/assetPaths.ts';
import { dom, domCache } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction, isRecordLike, isString } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

class Branding {
    transitionDuration = LOGO_TRANSITION_DURATION_MS;
    preloadedImages: Record<string, HTMLImageElement> = {};
    initialized = false;
    resources = new ResourceTracker();
    readonly #descriptor: BrandingDescriptor;

    constructor(descriptor: BrandingDescriptor) {
        this.#descriptor = descriptor;
    }

    queryUI(selector: string, context: HTMLElement | null = null): Element[] {
        domCache.invalidate(selector);
        return dom.resolveAll(selector, context);
    }

    async initialize(): Promise<void> {
        if (this.initialized) return;
        this.initialized = true;

        await this.preloadLogos();
        this.updateAllLogos();
        this.setupThemeListener();
    }

    async preloadLogos(): Promise<void> {
        await preloadBrandLogos(this.#descriptor, this.preloadedImages);
    }

    setupThemeListener(): void {
        const root = dom.getDocumentElement();
        const body = dom.getBody();
        const observer = new MutationObserver((mutations) => {
            const isRelevantChange = mutations.some((match) => match.attributeName === 'class' && (match.target === root || match.target === body));
            if (isRelevantChange) {
                this.updateAllLogos();
            }
        });

        const observerConfig = {
            attributes: true,
            attributeFilter: ['class']
        };
        observer.observe(root, observerConfig);
        observer.observe(body, observerConfig);
        this.resources.track(observer, (tracked) => tracked.disconnect());
    }

    getCurrentTheme(): Theme {
        return detectCurrentBrandTheme(dom);
    }

    getLogoVariant(element: Element): BrandVariant | null {
        return resolveBrandVariantOverride(dom.getData(element, 'logoVariant'));
    }

    resolveLogoTransition(): string {
        return `opacity ${this.transitionDuration}ms ease-in-out`;
    }

    getLogoPath(type: string, theme?: string, variant: BrandVariant | null = null): string | null {
        return resolveBrandLogoPath(this.#descriptor, type, theme, variant, () => this.getCurrentTheme());
    }

    updateAllLogos(): void {
        const currentTheme = this.getCurrentTheme();
        const logoElements = this.queryUI('[data-logo-type], .sidebar-logo').filter((element): element is HTMLImageElement => element instanceof HTMLImageElement && !element.closest('#page-preloader'));

        for (const element of logoElements) {
            const logoType = dom.getData(element, 'logoType') || 'ui';
            this.updateLogoElement(element, logoType, currentTheme);
        }
    }

    updateLogoElement(element: Element, logoType: string, theme?: string): void {
        if (element.closest('#page-preloader')) return;
        if (!(element instanceof HTMLImageElement)) {
            throw new TypeError('Branding.updateLogoElement expects an HTMLImageElement');
        }

        const currentTheme = resolveBrandTheme(theme, () => this.getCurrentTheme());
        const variant = resolveBrandVariant(this.#descriptor, this.getLogoVariant(element));
        const resolvedType = resolveBrandLogoType(logoType);
        const config = resolveBrandVariantLogoConfig(this.#descriptor, resolvedType, variant);
        const rawPath = currentTheme === 'light' ? config.light : config.dark;
        const newSrc = resolveAssetPath(rawPath);
        if (!newSrc) {
            throw new Error(`Branding logo path resolution failed: ${rawPath}`);
        }

        const visibilityHint = (dom.getData(element, 'visible') ?? '').toLowerCase();
        const shouldShow = !['false', '0', 'hidden', 'off', 'no'].includes(visibilityHint);

        const preloadedKey = buildBrandPreloadedKey(variant, resolvedType, currentTheme);
        const preloadedImg = this.preloadedImages[preloadedKey];

        if (preloadedImg && shouldShow) {
            dom.setProperty(element, 'src', newSrc);
            dom.setStyles(element, {
                transition: this.resolveLogoTransition(),
                opacity: '1'
            });
        } else {
            dom.setStyle(element, 'opacity', '0');
            if (shouldShow) {
                const previousSrc = element.src;
                const img = new Image();
                img.onload = () => {
                    dom.setProperty(element, 'src', newSrc);
                    dom.setStyles(element, {
                        transition: this.resolveLogoTransition(),
                        opacity: '1'
                    });
                };
                img.onerror = () => {
                    errorHandler.warn('Branding', 'Failed to load logo image', { src: newSrc });
                    if (previousSrc) {
                        dom.setProperty(element, 'src', previousSrc);
                    }
                    dom.setStyles(element, {
                        transition: this.resolveLogoTransition(),
                        opacity: '1'
                    });
                };
                img.src = newSrc;
            }
        }

        dom.setData(element, 'logoCurrentVisibility', String(shouldShow));
    }

    transitionLogo(element: HTMLImageElement, newSrc: string, shouldShow = true): void {
        const isInitialLoad = !element.src || element.src.endsWith('/');

        const finalizeVisibility = (): void => {
            dom.setStyle(element, 'opacity', shouldShow ? '1' : '0');
            dom.setData(element, 'logoCurrentVisibility', String(shouldShow));
        };

        if (isInitialLoad) {
            dom.setProperty(element, 'src', newSrc);
            const reveal = async (): Promise<void> => {
                await waitForBrandImageLoaded(element, 500);
                finalizeVisibility();
            };
            void reveal().catch((error) => {
                errorHandler.warn('Branding', 'Logo reveal failed', error);
            });
        } else {
            dom.setStyle(element, 'opacity', '0');
            this.resources.setTimeout(() => {
                const run = async (): Promise<void> => {
                    dom.setProperty(element, 'src', newSrc);
                    await waitForBrandImageLoaded(element, 1000);
                    finalizeVisibility();
                };
                void run().catch((error) => {
                    errorHandler.warn('Branding', 'Logo transition failed', error);
                });
            }, this.transitionDuration / 2);
        }
    }

    dispose(): void {
        this.resources.cleanup();
        this.initialized = false;
    }

    updateLogo(selector: string | HTMLElement, logoType: string, theme: string | null = null): void {
        const elements = isString(selector) ? this.queryUI(selector) : [selector];
        for (const element of elements) {
            this.updateLogoElement(element, logoType, theme ?? undefined);
        }
    }

    createLogoElement(logoType: string, className = ''): HTMLImageElement | null {
        const logoSrc = this.getLogoPath(logoType, this.getCurrentTheme());
        if (!logoSrc) return null;

        const img = dom.getDocument().createElement('img');
        dom.setProperty(img, 'src', logoSrc);
        dom.setProperty(img, 'alt', 'SoAI');
        const classNames = `logo logo-${logoType} logo-transition ${className}`.trim();
        dom.addClass(img, classNames.split(/\s+/).filter(Boolean));
        dom.setData(img, 'logoType', logoType);
        return img;
    }

    getAspectRatio(logoType: string): string {
        const resolved = resolveBrandLogoType(logoType);
        return resolveBrandVariantLogoConfig(this.#descriptor, resolved, resolveBrandVariant(this.#descriptor)).aspectRatio;
    }

    forceRefresh(): void {
        this.updateAllLogos();
    }

    getLogoInfo(): BrandingInfo {
        const theme = this.getCurrentTheme();
        const variant = resolveBrandVariant(this.#descriptor);
        const info: Record<string, LogoInfo> = {};

        for (const type of LOGO_TYPES) {
            info[type] = {
                currentPath: this.getLogoPath(type, theme),
                aspectRatio: this.getAspectRatio(type),
                preloaded: !!this.preloadedImages[buildBrandPreloadedKey(variant, type, theme)]
            };
        }

        return {
            currentTheme: theme,
            logos: info,
            initialized: this.initialized
        };
    }
}

const createBranding = (descriptor: BrandingDescriptor): Branding => new Branding(descriptor);

const isBrandingService = <T>(value: T): value is T & Branding => {
    if (!isRecordLike(value)) return false;
    return 'initialize' in value && isFunction(value.initialize) && 'updateAllLogos' in value && isFunction(value.updateAllLogos);
};

const getBranding = (): Branding => {
    const candidate = resolveKernelService('core.branding');
    if (!isBrandingService(candidate)) {
        throw new Error('core.branding is not registered');
    }
    return candidate;
};

export { Branding, createBranding, getBranding };
