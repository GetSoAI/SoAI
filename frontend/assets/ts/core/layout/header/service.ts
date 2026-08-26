/* SoAI - Shared layout header service [frontend/assets/ts/core/layout/header/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getIconFromString, getIconFromStringSync } from '@core/ui/icons/iconservice/public.ts';
import { isArray } from '@core/typeGuards.ts';
import { optionalChildElement } from '@core/layout/header/dom.ts';
import type { HeaderIconOptions } from '@core/layout/header/state.ts';
import type { IconApplyConfig, IconsService } from '@core/layout/HeaderInterface.ts';
import type { TrustedHtml } from '@core/security/public.ts';

const createHeaderIconsService = (replaceNodeMarkup: (node: Element, markup: TrustedHtml) => void): IconsService => {
    const iconCache = new Map<string, TrustedHtml>();
    return {
        reset: (): void => {
            iconCache.clear();
        },
        get: (name: string, options: HeaderIconOptions = {}): TrustedHtml | undefined => {
            const { size, strokeWidth } = options;
            const key = `${name}:${size ?? ''}:${strokeWidth ?? ''}`;
            if (iconCache.has(key)) {
                return iconCache.get(key);
            }

            const iconOptions: { size?: number; strokeWidth?: number } = {};
            const parsedSize = typeof size === 'number' ? size : typeof size === 'string' ? Number(size) : NaN;
            if (Number.isFinite(parsedSize) && parsedSize > 0) {
                iconOptions.size = parsedSize;
            }

            const parsedStroke = typeof strokeWidth === 'number' ? strokeWidth : typeof strokeWidth === 'string' ? Number(strokeWidth) : NaN;
            if (Number.isFinite(parsedStroke) && parsedStroke > 0) {
                iconOptions.strokeWidth = parsedStroke;
            }

            const markup = getIconFromStringSync(name, iconOptions);
            iconCache.set(key, markup);
            return markup;
        },
        apply: async (targets: IconApplyConfig[] = []): Promise<void> => {
            const list = isArray(targets) ? targets : [];
            const tasks = list
                .filter((entry) => Boolean(entry))
                .map(async ({ element, selector, icon, replace = false }) => {
                    if (!element || !icon) {
                        return;
                    }
                    const node = selector ? optionalChildElement(element, selector) : element;
                    if (!node) {
                        return;
                    }
                    const markup = await getIconFromString(icon);
                    if (replace) {
                        replaceNodeMarkup(node, markup);
                        return;
                    }
                    dom.setHTML(node, markup, { escape: false });
                });
            if (tasks.length > 0) {
                await Promise.all(tasks);
            }
        }
    };
};

export { createHeaderIconsService };
