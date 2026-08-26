/* SoAI - Shared UI primitives view effects [frontend/assets/ts/core/uiprimitives/view/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import type { ButtonConfig } from '@core/uiprimitives/types.ts';

const composeCollectionButtonContent = (config: ButtonConfig, resolveIcon: (icon: ButtonConfig['icon']) => string, escapeHtml: (value: string) => string): string => {
    const icon = config.icon ? resolveIcon(config.icon) : '';
    const label = !isNullOrUndefined(config.label) ? escapeHtml(String(config.label)) : '';
    const iconMarkup = icon ? renderIconSlot(icon).html : '';
    return iconMarkup && label ? `${iconMarkup}<span>${label}</span>` : iconMarkup || label;
};

export { composeCollectionButtonContent };
