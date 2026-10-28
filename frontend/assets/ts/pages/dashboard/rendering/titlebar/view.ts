/* SoAI - Dashboard titlebar control rendering [frontend/assets/ts/pages/dashboard/rendering/titlebar/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiAttributes, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface DashboardTitlebarButtonOptions {
    id: string;
    action: string;
    label: string;
    icon: IconName;
    variant?: 'ui-variant-neutral' | 'ui-variant-accent' | 'ui-variant-danger';
    pressed?: boolean;
}

const renderDashboardTitlebarButton = (options: DashboardTitlebarButtonOptions): TrustedHtml => {
    const icon = getIconSync(options.icon, { size: 14, strokeWidth: 1.8 });
    const state = uiAttributes({ 'aria-pressed': options.pressed === undefined ? undefined : String(options.pressed) });
    return uiHtml`<button type="button" class="ui-icon-button ui-icon-button--titlebar ${uiAttr(options.variant ?? 'ui-variant-neutral')}" id="${uiAttr(options.id)}" data-action="${uiAttr(options.action)}" aria-label="${uiAttr(options.label)}" data-tooltip="${uiAttr(options.label)}"${state}>${icon}</button>`;
};

export { renderDashboardTitlebarButton };
