/* SoAI - Frontend icon service ownership [frontend/assets/ts/core/ui/icons/iconservice/IconService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { hasFunctionProperties, isArray, isObject, isPlainObject, isString } from '@core/typeGuards.ts';
import { STATIC_ICON_REGISTRY, type IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { DEFAULT_ICON_SIZE, DEFAULT_ICON_STROKE } from '@core/ui/icons/iconservice/constants.ts';
import { applySvgAttributes, applySvgOptions, isDevBuild, isIconName, listAllIconNames, mergeDefaultIconOptions, normalizeOptions, renderMissingIcon, variantKey } from '@core/ui/icons/iconservice/service.ts';
import type { IconAttributes, IconOptions, NormalizedIconOptions } from '@core/ui/icons/iconservice/types.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

class IconService {
    readonly #variants: Map<string, string>;
    readonly #trustedVariants: Map<string, TrustedHtml>;

    constructor() {
        this.#variants = new Map();
        this.#trustedVariants = new Map();
    }

    #renderCore(name: IconName, options: NormalizedIconOptions): string {
        const cacheKey = variantKey(name, options);
        const cached = this.#variants.get(cacheKey);
        if (cached) {
            return cached;
        }

        const registryValue = STATIC_ICON_REGISTRY[name];
        const raw = isString(registryValue) && registryValue.trim() ? registryValue : '';
        let rendered = '';
        let renderError: Error | null = null;
        if (raw) {
            try {
                rendered = applySvgOptions(raw, options, name);
            } catch (error) {
                renderError = ensureError(error);
                if (isDevBuild()) {
                    throw renderError;
                }
            }
        }

        if (!rendered) {
            const message = `Icon "${name}" is missing from the registry or rendered empty markup`;
            if (isDevBuild()) {
                throw new Error(message);
            }
            errorHandler.warn('IconService', message, renderError);
            const missing = renderMissingIcon(name, options);
            this.#variants.set(cacheKey, missing);
            return missing;
        }

        this.#variants.set(cacheKey, rendered);
        return rendered;
    }

    getIconMarkupSync(name: IconName, options: IconOptions | undefined = undefined): string {
        const normalized = mergeDefaultIconOptions(name, options);
        const core = this.#renderCore(name, normalized);
        const attrs: IconAttributes = isPlainObject(options?.attributes) ? options.attributes : {};
        return applySvgAttributes(core, attrs);
    }

    getIconSync(name: IconName, options: IconOptions | undefined = undefined): TrustedHtml {
        if (isPlainObject(options?.attributes) && Object.keys(options.attributes).length > 0) {
            return toTrustedUiHtml(this.getIconMarkupSync(name, options));
        }
        const cacheKey = variantKey(name, mergeDefaultIconOptions(name, options));
        const cached = this.#trustedVariants.get(cacheKey);
        if (cached) {
            return cached;
        }
        const trusted = toTrustedUiHtml(this.getIconMarkupSync(name, options));
        this.#trustedVariants.set(cacheKey, trusted);
        return trusted;
    }

    async getIcon(name: IconName, options: IconOptions | undefined = undefined): Promise<TrustedHtml> {
        return this.getIconSync(name, options);
    }

    preloadIcons(names: readonly IconName[]): Promise<PromiseSettledResult<TrustedHtml>[]> {
        if (!isArray(names)) {
            return Promise.resolve([]);
        }
        return Promise.allSettled(names.map((name) => this.getIcon(name)));
    }

    preloadCommonIcons(): Promise<PromiseSettledResult<TrustedHtml>[]> {
        return this.preloadIcons(listAllIconNames());
    }
}

const ICON_SERVICE_ID = 'core.iconService';

interface IconServiceApi {
    getIconSync: (name: IconName, options?: IconOptions | undefined) => TrustedHtml;
    getIcon: (name: IconName, options?: IconOptions | undefined) => Promise<TrustedHtml>;
    preloadCommonIcons: () => Promise<PromiseSettledResult<TrustedHtml>[]>;
}

const isIconServiceApi = <T>(value: T): value is T & IconServiceApi => isObject(value) && hasFunctionProperties(value, ['getIconSync', 'getIcon', 'preloadCommonIcons']);

const createIconService = (): IconService => new IconService();

const getIconService = (): IconServiceApi => {
    const candidate = resolveKernelService(ICON_SERVICE_ID);
    if (!isIconServiceApi(candidate)) {
        throw new Error(`${ICON_SERVICE_ID} is not registered`);
    }
    return candidate;
};

const getIconSync = (name: IconName, options: IconOptions | undefined = undefined): TrustedHtml => {
    return getIconService().getIconSync(name, options);
};

const getIcon = async (name: IconName, options: IconOptions | undefined = undefined): Promise<TrustedHtml> => {
    return getIconService().getIcon(name, options);
};

const getIconFromStringSync = (name: string, options: IconOptions | undefined = undefined): TrustedHtml => {
    if (isIconName(name)) {
        return getIconService().getIconSync(name, options);
    }
    const normalized = normalizeOptions(options);
    const message = `Unknown icon name: ${name}`;
    if (isDevBuild()) {
        errorHandler.error('IconService', message);
        throw new Error(message);
    }
    errorHandler.warn('IconService', message);
    return toTrustedUiHtml(
        renderMissingIcon(name, {
            ...normalized,
            size: normalized.size ?? DEFAULT_ICON_SIZE,
            strokeWidth: normalized.strokeWidth ?? DEFAULT_ICON_STROKE
        })
    );
};

const getIconFromString = async (name: string, options: IconOptions | undefined = undefined): Promise<TrustedHtml> => {
    return getIconFromStringSync(name, options);
};

const preloadCommonIcons = (): Promise<PromiseSettledResult<TrustedHtml>[]> => getIconService().preloadCommonIcons();

const requireIconName = (value: string | null, label: string = 'IconName'): IconName => {
    if (isIconName(value)) {
        return value;
    }
    throw new Error(`${label} must be a known icon name. Received: ${String(value)}`);
};

export { getIcon, getIconFromString, getIconFromStringSync, getIconSync, isIconName, preloadCommonIcons, requireIconName };
export type { IconAttributes, IconOptions };
export { IconService, getIconService, createIconService, ICON_SERVICE_ID };
