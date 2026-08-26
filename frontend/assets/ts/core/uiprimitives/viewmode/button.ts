/* SoAI - Shared UI primitives button [frontend/assets/ts/core/uiprimitives/viewmode/button.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { ViewModeOption } from '@core/uiprimitives/viewmode/types.ts';

const applyViewModeButton = (button: HTMLButtonElement, option: ViewModeOption, renderIcon: (option: ViewModeOption) => TrustedHtml): void => {
    const iconMarkup = renderIcon(option);
    replaceChildrenFromTrustedHtml({
        element: button,
        html: uiHtml`${iconMarkup}<span>${option.label}</span>`
    });
    button.setAttribute('aria-pressed', option.pressed ? 'true' : 'false');
    button.setAttribute('aria-label', option.label);
    setTooltipText(button, option.label);
};

export { applyViewModeButton };
