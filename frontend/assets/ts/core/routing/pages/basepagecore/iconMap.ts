/* SoAI - Shared routing icon map [frontend/assets/ts/core/routing/pages/basepagecore/iconMap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err } from '@core/routing/pages/basepagecore/actions.ts';
import type { IconDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { isIconName, requireIconName, type IconOptions } from '@core/ui/icons/iconservice/public.ts';

interface ApplyPageIconMapOptions {
    pageId: string;
    iconMap: Record<string, IconDefinition>;
    queryUI: (selector: string) => Element[];
    updateHTML: (element: Element, html: TrustedHtml | string, options?: { escape?: boolean }) => void;
    resolver: (name: IconName, options?: IconOptions) => TrustedHtml;
}

const normalizePageIconDefinition = (definition: IconDefinition): { name: IconName; options: IconOptions | undefined } => {
    if (isArray(definition)) {
        const name = requireIconName(definition[0], 'Icon name');
        const options = definition.length > 1 && definition[1] ? definition[1] : undefined;
        return { name, options };
    }
    if (isString(definition)) {
        if (isIconName(definition)) {
            return { name: definition, options: undefined };
        }
        return { name: requireIconName(definition, 'Icon name'), options: undefined };
    }
    if (isObject(definition)) {
        const nameCandidate = definition.name ?? definition.icon ?? null;
        const name = requireIconName(nameCandidate, 'Icon name');
        return { name, options: definition.options };
    }
    throw err('Invalid icon definition');
};

const applyPageIconMap = (options: ApplyPageIconMapOptions): void => {
    if (!isObject(options.iconMap)) {
        throw err(`${options.pageId} icon map must be an object`);
    }
    for (const [selector, definition] of Object.entries(options.iconMap)) {
        const { name, options: iconOptions } = normalizePageIconDefinition(definition);
        const iconHtml = options.resolver(name, iconOptions);
        const elements = options.queryUI(selector);
        if (elements.length === 0) {
            throw err(`applyIconMap: no elements found for selector "${selector}"`);
        }
        for (const element of elements) {
            options.updateHTML(element, iconHtml, { escape: false });
        }
    }
};

export { applyPageIconMap };
