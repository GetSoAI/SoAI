/* SoAI - Local failure presentation with page reload recovery [frontend/assets/ts/core/ui/reloadFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { uiHtml, uiAttr } from '@core/security/uiHtml.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';

const renderReloadFailure = (message: string): TrustedHtml => {
    const reloadLabel = i18n.t('common.actions.reloadPage');
    return uiHtml`<div class="reload-failure" role="status"><p>${message}</p><button type="button" class="ui-button ui-variant-neutral" data-action="reload-page" aria-label="${uiAttr(reloadLabel)}" data-tooltip="${uiAttr(reloadLabel)}">${reloadLabel}</button></div>`;
};

const bindReloadFailure = (root: HTMLElement): (() => void) => {
    const controller = new AbortController();
    bindDataActionListener({
        root,
        signal: controller.signal,
        eventType: 'click',
        stopPropagation: true,
        isAction: (value): value is 'reload-page' => value === 'reload-page',
        onAction: () => {
            controller.abort();
            window.location.reload();
        }
    });
    return () => controller.abort();
};

export { renderReloadFailure, bindReloadFailure };
