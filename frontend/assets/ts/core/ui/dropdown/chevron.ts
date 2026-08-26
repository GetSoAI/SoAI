/* SoAI - Shared UI chevron [frontend/assets/ts/core/ui/dropdown/chevron.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';

type ResolveDropdownIcon = (name: IconName, options?: IconOptions) => TrustedHtml;

const DROPDOWN_CHEVRON_OPTIONS: IconOptions = Object.freeze({
    size: 16,
    strokeWidth: 1.5
});

const resolveDropdownChevronClassName = (className: string): string => {
    const classNames = className.split(/\s+/).filter(Boolean);
    if (!classNames.includes('ui-icon')) {
        classNames.push('ui-icon');
    }
    return classNames.join(' ');
};

const renderDropdownChevron = (resolveIcon: ResolveDropdownIcon, className: string = 'dropdown-chevron'): string => {
    return renderIconSlot(resolveIcon('chevron-down', DROPDOWN_CHEVRON_OPTIONS), { className: resolveDropdownChevronClassName(className) }).html;
};

export { DROPDOWN_CHEVRON_OPTIONS, renderDropdownChevron };
export type { ResolveDropdownIcon };
