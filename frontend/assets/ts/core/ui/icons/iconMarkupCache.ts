/* SoAI - Bounded TrustedHtml icon markup cache [frontend/assets/ts/core/ui/icons/iconMarkupCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

class IconMarkupCache {
    readonly #cache: Map<string, TrustedHtml>;
    readonly #maxEntries: number;

    constructor(options: { maxEntries?: number } = {}) {
        const maxEntries = options.maxEntries ?? 100;
        if (!Number.isFinite(maxEntries) || maxEntries <= 0) {
            throw new Error(`IconMarkupCache requires a positive maxEntries value, received: ${String(maxEntries)}`);
        }
        this.#cache = new Map();
        this.#maxEntries = maxEntries;
    }

    clear(): void {
        this.#cache.clear();
    }

    get(iconName: IconName, options: IconOptions, resolve: (iconName: IconName, options: IconOptions) => TrustedHtml): TrustedHtml {
        const cacheKey = `${iconName}::${JSON.stringify(options)}`;
        const existing = this.#cache.get(cacheKey);
        if (existing !== undefined) {
            return existing;
        }

        if (this.#cache.size >= this.#maxEntries) {
            const oldest = this.#cache.keys().next().value;
            if (typeof oldest === 'string' && oldest) {
                this.#cache.delete(oldest);
            }
        }

        const resolved = resolve(iconName, options);
        if (!isTrustedHtml(resolved) || !resolved.html.trim()) {
            throw new Error(`IconMarkupCache resolved empty markup for "${iconName}"`);
        }
        this.#cache.set(cacheKey, resolved);
        return resolved;
    }
}

export { IconMarkupCache };
