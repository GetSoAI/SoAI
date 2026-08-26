/* SoAI - Shared UI tabs rendering [frontend/assets/ts/core/ui/controls/tabs/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { isTrustedHtml } from '@core/security/htmlSanitizer.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { createOverflowNavButtonMarkup } from '@core/ui/controls/OverflowNav.ts';
import { isArray } from '@core/typeGuards.ts';
import type { RightButtonConfig, TabConfig } from '@core/ui/controls/tabs/types.ts';

const renderIconMarkup = (value: TrustedHtml | string | undefined): string => {
    if (!value) {
        return '';
    }
    if (isTrustedHtml(value)) {
        return value.html;
    }
    return value;
};

const renderTabsMarkup = (tabs: TabConfig[], className: string): TrustedHtml =>
    toTrustedUiHtml(
        tabs
            .map((tab) => {
                const label = securityApi.escapeAttribute(String(tab.label ?? ''));
                const notify = tab.notifyBadge ? securityApi.escapeAttribute(String(tab.notifyBadge)) : '';
                const iconMarkup = renderIconMarkup(tab.icon);
                return `
    <button class="${className}-tab" data-tab="${tab.id}" id="${tab.id}-tab" type="button" aria-label="${label}" data-tooltip="${label}">
        ${iconMarkup}
        <span class="${className}-tab-label">${tab.label}</span>
        ${tab.badge ? `<span class="tab-notify-badge" id="${tab.id}-badge">${tab.badge}</span>` : ''}
        ${tab.notifyBadge ? `<span class="tab-notify-badge" id="${tab.id}-notify" aria-label="${notify} notifications">${tab.notifyBadge}</span>` : ''}
    </button>
    `;
            })
            .join('')
    );

const renderRightButtonsMarkup = (activeTab: string | null, rightButtons: Record<string, RightButtonConfig[]>): TrustedHtml => {
    const buttons = activeTab ? rightButtons[activeTab] : undefined;
    if (!buttons) {
        return EMPTY_UI_HTML;
    }
    if (!isArray(buttons)) {
        throw new TypeError(`Right buttons for tab ${activeTab} must be an array`);
    }
    return toTrustedUiHtml(
        buttons
            .map((button) => {
                const label = securityApi.escapeAttribute(String(button.label ?? ''));
                const iconMarkup = renderIconMarkup(button.icon);
                return `
    <button class="ui-button ${button.className ?? ''}" id="${button.id}" ${button.disabled ? 'disabled' : ''} type="button" aria-label="${label}" data-tooltip="${label}">
        ${iconMarkup}
        <span>${button.label}</span>
    </button>
    `;
            })
            .join('')
    );
};

const renderNavButtonMarkup = (className: string, direction: 'left' | 'right'): TrustedHtml => {
    const isLeft = direction === 'left';
    const label = isLeft ? i18n.t('tabs.scrollLeft') : i18n.t('tabs.scrollRight');
    const iconName = isLeft ? 'chevron-left' : 'chevron-right';
    return toTrustedUiHtml(
        createOverflowNavButtonMarkup({
            direction,
            className: `${className}-nav-button ${className}-nav-button--${direction}`,
            label,
            iconName,
            iconOptions: { size: 24, strokeWidth: 1.5 }
        })
    );
};

const renderContainerMarkup = (className: string, tabs: TabConfig[], activeTab: string | null, rightButtons: Record<string, RightButtonConfig[]>, enableOverflowNav: boolean): TrustedHtml => {
    const leftButton = enableOverflowNav ? renderNavButtonMarkup(className, 'left') : EMPTY_UI_HTML;
    const rightButton = enableOverflowNav ? renderNavButtonMarkup(className, 'right') : EMPTY_UI_HTML;
    return toTrustedUiHtml(`
        <div class="${className}-container">
            <div class="${className}-nav-wrapper">
                ${leftButton.html}
                <nav class="${className}-nav">${renderTabsMarkup(tabs, className).html}</nav>
                ${rightButton.html}
            </div>
            <div class="${className}-buttons" id="${className}-buttons">${renderRightButtonsMarkup(activeTab, rightButtons).html}</div>
        </div>
        `);
};

export { renderContainerMarkup, renderRightButtonsMarkup };
