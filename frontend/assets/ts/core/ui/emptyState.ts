/* SoAI - Shared UI empty state [frontend/assets/ts/core/ui/emptyState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isTrustedHtml, securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';

interface EmptyStateRenderOptions {
    icon?: TrustedHtml | string | null | undefined;
    title: string;
    message?: string | null | undefined;
    className?: string | undefined;
    iconClassName?: string | undefined;
}

const renderTrustedOrText = (value: TrustedHtml | string | null | undefined): string => {
    if (value === null || value === undefined) {
        return '';
    }
    if (isTrustedHtml(value)) {
        return value.html;
    }
    return securityApi.escapeHtml(value);
};

const renderEmptyState = (options: EmptyStateRenderOptions): TrustedHtml => {
    const className = options.className?.trim() || 'ui-empty-state';
    const iconClassName = options.iconClassName?.trim() || 'ui-empty-state__icon';
    const iconMarkup = renderTrustedOrText(options.icon);
    const messageMarkup = options.message ? `<p>${securityApi.escapeHtml(options.message)}</p>` : '';
    return toTrustedUiHtml(`<div class="${securityApi.escapeAttribute(className)}">${iconMarkup ? `<div class="${securityApi.escapeAttribute(iconClassName)}">${iconMarkup}</div>` : ''}<h3>${securityApi.escapeHtml(options.title)}</h3>${messageMarkup}</div>`);
};

export { renderEmptyState };
export type { EmptyStateRenderOptions };
