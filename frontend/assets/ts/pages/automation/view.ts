/* SoAI - Automation page rendering [frontend/assets/ts/pages/automation/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { AUTOMATION_ACTION_CYCLE_VIEW, AUTOMATION_ACTION_NAV_NEXT, AUTOMATION_ACTION_NAV_PREVIOUS, AUTOMATION_ACTION_NAV_TODAY, AUTOMATION_ACTION_OPEN_CALENDAR_SETTINGS_MODAL, AUTOMATION_ACTION_OPEN_CREATE_MODAL, AUTOMATION_ACTION_RESET_PREFERENCES, AUTOMATION_ACTION_SET_VIEW, AUTOMATION_ACTION_TOGGLE_REGISTRY_OVERLAY } from '@features/automation/public.ts';

interface RenderAutomationPageDependencies {
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

const renderAutomationPageView = (dependencies: RenderAutomationPageDependencies): TrustedHtml => {
    const prevLabel = i18n.t('automation.toolbar.previous');
    const nextLabel = i18n.t('automation.toolbar.next');
    const todayLabel = i18n.t('automation.toolbar.today');
    const createLabel = i18n.t('automation.toolbar.create');
    const registryOverlayToggleLabel = i18n.t('automation.toolbar.showRegistry');
    const calendarSettingsLabel = i18n.t('automation.toolbar.calendarSettings');
    const moreActionsLabel = i18n.t('header.actions.moreActions');

    const monthLabel = i18n.t('automation.views.month');
    const weekLabel = i18n.t('automation.views.week');
    const dayLabel = i18n.t('automation.views.day');

    const iconPrev = renderIconSlot(dependencies.getIconSync('chevron-up', { size: 16, strokeWidth: 2 }));
    const iconNext = renderIconSlot(dependencies.getIconSync('chevron-down', { size: 16, strokeWidth: 2 }));
    const iconAdd = renderIconSlot(dependencies.getIconSync('add', { size: 16, strokeWidth: 1.8 }));
    const iconSettings = renderIconSlot(dependencies.getIconSync('model-config', { size: 16, strokeWidth: 1.5 }));
    const iconMore = renderIconSlot(dependencies.getIconSync('ellipsis', { size: 20, strokeWidth: 1.5 }));
    const iconRegistryOverlay = renderIconSlot(dependencies.getIconSync('panel-hidden', { size: 16, strokeWidth: 1.5 }));
    const iconViewMonth = renderIconSlot(dependencies.getIconSync('view-month', { size: 16 }), { className: 'ui-icon automation-view-toggle-icon' });
    const iconViewWeek = renderIconSlot(dependencies.getIconSync('view-week', { size: 16 }), { className: 'ui-icon automation-view-toggle-icon' });
    const iconViewDay = renderIconSlot(dependencies.getIconSync('view-day', { size: 16 }), { className: 'ui-icon automation-view-toggle-icon' });

    const preferencesCorruptTitle = i18n.t('automation.preferencesCorrupt.title');
    const preferencesCorruptMessage = i18n.t('automation.preferencesCorrupt.message');
    const preferencesCorruptReset = i18n.t('automation.preferencesCorrupt.reset');
    const loadingLabel = i18n.t('common.loading');

    return uiHtml`<div id="automation-root" class="automation-container" data-section="automation" data-page-transition-surface="true" role="main">
        <div id="automation-preferences-corrupt-overlay" class="automation-blocking-overlay u-hidden" role="alertdialog" aria-modal="true" aria-labelledby="automation-preferences-corrupt-title">
            <div class="automation-blocking-card surface-card">
                <h2 id="automation-preferences-corrupt-title" class="automation-blocking-title">${uiText(preferencesCorruptTitle)}</h2>
                <p class="automation-blocking-message">${uiText(preferencesCorruptMessage)}</p>
                <button type="button" class="ui-button ui-variant-accent" data-action="${uiAttr(AUTOMATION_ACTION_RESET_PREFERENCES)}" aria-label="${uiAttr(preferencesCorruptReset)}" data-tooltip="${uiAttr(preferencesCorruptReset)}">${uiText(preferencesCorruptReset)}</button>
            </div>
        </div>
        <div id="automation-content-wrapper" class="automation-content-wrapper">
            <div class="automation-toolbar surface-card">
                <div class="automation-toolbar-group automation-toolbar-group--navigation">
                    <button type="button" class="ui-button ui-icon-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_NAV_PREVIOUS)}" aria-label="${uiAttr(prevLabel)}" data-tooltip="${uiAttr(prevLabel)}">${iconPrev}</button>
                    <button id="automation-today-button" type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_NAV_TODAY)}" aria-label="${uiAttr(todayLabel)}" data-tooltip="${uiAttr(todayLabel)}">${uiText(todayLabel)}</button>
                    <button type="button" class="ui-button ui-icon-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_NAV_NEXT)}" aria-label="${uiAttr(nextLabel)}" data-tooltip="${uiAttr(nextLabel)}">${iconNext}</button>
                    <div id="automation-range-title" class="automation-range-title"></div>
                </div>
                <div class="automation-toolbar-group automation-toolbar-group--actions">
                    <button id="automation-registry-overlay-toggle" type="button" class="ui-icon-button automation-registry-overlay-toggle" data-action="${uiAttr(AUTOMATION_ACTION_TOGGLE_REGISTRY_OVERLAY)}" aria-label="${uiAttr(registryOverlayToggleLabel)}" data-tooltip="${uiAttr(registryOverlayToggleLabel)}">${iconRegistryOverlay}</button>
                    <div class="page-actions automation-toolbar-overflow">
                        <button type="button" class="ui-icon-button page-actions__trigger automation-toolbar-overflow-trigger" aria-label="${uiAttr(moreActionsLabel)}" data-tooltip="${uiAttr(moreActionsLabel)}" aria-haspopup="true" aria-expanded="false">${iconMore}</button>
                        <div class="page-actions__menu page-actions__menu--split automation-toolbar-overflow-menu" role="toolbar">
                            <div id="automation-view-toggle" class="automation-view-toggle" role="tablist" aria-label="${uiAttr(i18n.t('common.view'))}">
                                <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_SET_VIEW)}" data-view="month" role="tab" aria-selected="false" aria-label="${uiAttr(monthLabel)}" data-tooltip="${uiAttr(monthLabel)}">${iconViewMonth}${uiText(monthLabel)}</button>
                                <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_SET_VIEW)}" data-view="week" role="tab" aria-selected="false" aria-label="${uiAttr(weekLabel)}" data-tooltip="${uiAttr(weekLabel)}">${iconViewWeek}${uiText(weekLabel)}</button>
                                <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(AUTOMATION_ACTION_SET_VIEW)}" data-view="day" role="tab" aria-selected="false" aria-label="${uiAttr(dayLabel)}" data-tooltip="${uiAttr(dayLabel)}">${iconViewDay}${uiText(dayLabel)}</button>
                                <button id="automation-view-cycle-button" type="button" class="ui-button ui-variant-neutral automation-view-cycle-button" data-action="${uiAttr(AUTOMATION_ACTION_CYCLE_VIEW)}" aria-label="${uiAttr(i18n.t('common.view'))}" data-tooltip="${uiAttr(i18n.t('common.view'))}">${uiText(monthLabel)}</button>
                            </div>
                            <button id="automation-calendar-settings-button" type="button" class="ui-button ui-variant-neutral automation-toolbar-action-button automation-toolbar-action-button--settings" data-action="${uiAttr(AUTOMATION_ACTION_OPEN_CALENDAR_SETTINGS_MODAL)}" aria-label="${uiAttr(calendarSettingsLabel)}" data-tooltip="${uiAttr(calendarSettingsLabel)}">${iconSettings}<span class="automation-toolbar-button-label">${uiText(calendarSettingsLabel)}</span></button>
                            <button id="automation-create-button" type="button" class="ui-button ui-variant-accent automation-create-button" data-action="${uiAttr(AUTOMATION_ACTION_OPEN_CREATE_MODAL)}" aria-label="${uiAttr(createLabel)}" data-tooltip="${uiAttr(createLabel)}">${iconAdd}<span class="automation-create-button-label">${uiText(createLabel)}</span></button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="automation-split">
                <section class="automation-pane automation-pane--calendar">
                            <div class="automation-surface surface-card">
                        <div class="automation-surface-body">
                            <div id="automation-calendar-root" class="automation-calendar-root">
                                <div class="loading-container automation-calendar-loading">
                                    <div class="loading-spinner" aria-hidden="true"></div>
                                    <span class="loading-text">${uiText(loadingLabel)}</span>
                                </div>
                                <div class="automation-calendar-scroll" data-automation-scroll="calendar">
                                    <div class="automation-calendar-stream" data-automation-calendar-stage="true"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
                <div id="automation-splitter" class="automation-splitter" role="separator" aria-orientation="vertical"></div>
                <aside class="automation-pane automation-pane--registry">
                    <div class="automation-surface surface-card automation-registry">
                        <div class="automation-surface-body">
                            <div id="automation-registry-root" class="automation-registry-root">
                                <div id="automation-registry-scroll" class="automation-registry-scroll">
                                    <div id="automation-automations-root" class="automation-automations-root"></div>
                                    <div id="automation-window-runs-root" class="automation-window-runs-root"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    </div>`;
};
export { renderAutomationPageView };
