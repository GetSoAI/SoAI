/* SoAI - Automation page renderer [frontend/assets/ts/pages/automation/controllers/AutomationPageRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { isSameDay } from '@core/time/localCalendar.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { formatRangeTitle } from '@pages/automation/formatting/service.ts';
import { renderAutomationCalendar, type AutomationCalendarRenderCache } from '@pages/automation/controllers/automationCalendarPresentation.ts';
import { resolveAutomationWindow, type AutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import { queryAutomationViewToggleButtons, requireAutomationViewCycleButton } from '@pages/automation/dom.ts';
import { renderAutomationsListView } from '@pages/automation/rendering/automationsListView.ts';
import { renderWindowRunsListView } from '@pages/automation/rendering/windowRunsListView.ts';
import type { AutomationDefinition, AutomationZone } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';

interface RenderHost {
    ui: AutomationUiRefs;
    replaceElementContent: (element: Element, content: string | TrustedHtml, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
    hourHeightPx: number;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

const registryMarkupCache = new WeakMap<HTMLElement, string>();

const replaceCachedMarkup = (host: RenderHost, element: HTMLElement, markup: string): void => {
    if (registryMarkupCache.get(element) === markup) {
        return;
    }
    const trustedMarkup = toTrustedUiHtml(markup);
    host.replaceElementContent(element, trustedMarkup);
    registryMarkupCache.set(element, markup);
};

const applyAccentVariant = (button: HTMLButtonElement, isAccent: boolean): void => {
    button.classList.toggle('ui-variant-accent', isAccent);
    button.classList.toggle('ui-variant-neutral', !isAccent);
};

const isCurrentRange = (window: AutomationWindow, now: Date): boolean => {
    switch (window.viewMode) {
        case 'month':
            return window.focusDate.getFullYear() === now.getFullYear() && window.focusDate.getMonth() === now.getMonth();
        case 'week':
            for (const day of window.weekDays) {
                if (isSameDay(day, now)) {
                    return true;
                }
            }
            return false;
        case 'day':
            return isSameDay(window.day, now);
    }
};

const resolveViewModeLabel = (viewMode: string): string => {
    switch (viewMode) {
        case 'month':
            return i18n.t('automation.views.month');
        case 'week':
            return i18n.t('automation.views.week');
        case 'day':
            return i18n.t('automation.views.day');
        default:
            return i18n.t('automation.views.month');
    }
};

const renderViewToggle = (viewToggle: HTMLElement, active: string): void => {
    const buttons = queryAutomationViewToggleButtons(viewToggle);
    for (const btn of buttons) {
        const view = btn.dataset['view'] ?? '';
        const isActive = view === active;
        btn.classList.toggle('is-active', isActive);
        applyAccentVariant(btn, isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    }

    const cycleButton = requireAutomationViewCycleButton(viewToggle);
    const label = resolveViewModeLabel(active);
    cycleButton.textContent = label;
    cycleButton.setAttribute('aria-label', label);
    setTooltipText(cycleButton, label);
};

const renderRegistryOverlayToggle = (state: AutomationPageState, host: RenderHost): void => {
    const isOpen = state.registryOverlayOpen;
    const ui = host.ui;
    ui.root.classList.toggle('is-registry-overlay-open', isOpen);
    const label = isOpen ? i18n.t('automation.toolbar.showCalendar') : i18n.t('automation.toolbar.showRegistry');
    const iconName: IconName = isOpen ? 'panel-right-visible' : 'panel-hidden';
    const iconMarkup = renderIconSlot(host.getIconSync(iconName, { size: 16, strokeWidth: 1.5 }));
    host.replaceElementContent(ui.registryOverlayToggle, iconMarkup, { escape: false });
    ui.registryOverlayToggle.setAttribute('aria-label', label);
    setTooltipText(ui.registryOverlayToggle, label);
};

const renderTodayButtonState = (state: AutomationPageState, ui: AutomationUiRefs, now: Date): void => {
    const isToday = isSameDay(new Date(state.selectedDateUtcMs), now);
    applyAccentVariant(ui.todayButton, isToday);
};

const renderAutomationPage = (
    state: AutomationPageState,
    host: RenderHost,
    options: {
        monthMaxChipsPerDay: number;
        calendarCache: AutomationCalendarRenderCache;
        registryAutomations: readonly AutomationDefinition[];
        selectedAutomationId: string | null;
        runningAutomationIds: ReadonlySet<string>;
        registryLimit: number;
        registryOffset: number;
        registryHasMore: boolean;
        visibleWindowRuns: readonly AutomationZone[];
        preferencesCorrupt?: boolean | undefined;
        totalWindowRunsCount?: number | undefined;
        windowRunsSelectionActive?: boolean | undefined;
        windowRunsSelectedKeys?: ReadonlySet<string> | undefined;
    }
): string => {
    const isBlocked = options.preferencesCorrupt === true;
    host.ui.preferencesCorruptOverlay.classList.toggle('u-hidden', !isBlocked);
    host.ui.contentWrapper.setAttribute('aria-hidden', isBlocked ? 'true' : 'false');
    host.ui.root.classList.toggle('is-preferences-corrupt', isBlocked);
    if (isBlocked) {
        return '';
    }

    renderViewToggle(host.ui.viewToggle, state.viewMode);
    renderRegistryOverlayToggle(state, host);
    const window = resolveAutomationWindow(state);
    const now = new Date();
    renderTodayButtonState(state, host.ui, now);
    const registryScrollTop = host.ui.registryScroll.scrollTop;

    host.ui.rangeTitle.textContent = formatRangeTitle(window, state.calendarSettings);
    host.ui.rangeTitle.dataset['viewMode'] = window.viewMode;
    setTooltipText(host.ui.rangeTitle, host.ui.rangeTitle.textContent || '');
    host.ui.rangeTitle.classList.toggle('is-current-range', isCurrentRange(window, now));
    const renderedWindowSignature = renderAutomationCalendar(state, host, options.calendarCache, options.monthMaxChipsPerDay);
    replaceCachedMarkup(
        host,
        host.ui.automationsRoot,
        renderAutomationsListView({
            automations: options.registryAutomations,
            selectedAutomationId: options.selectedAutomationId,
            runningAutomationIds: options.runningAutomationIds,
            calendarSettings: state.calendarSettings,
            registryLimit: options.registryLimit,
            registryOffset: options.registryOffset,
            registryHasMore: options.registryHasMore,
            getIconSync: host.getIconSync
        })
    );
    replaceCachedMarkup(
        host,
        host.ui.windowRunsRoot,
        renderWindowRunsListView({
            zones: options.visibleWindowRuns,
            totalCount: options.totalWindowRunsCount ?? state.zones.length,
            selectedZoneKey: state.selectedZoneKey,
            calendarSettings: state.calendarSettings,
            selectionActive: options.windowRunsSelectionActive === true,
            selectedKeys: options.windowRunsSelectedKeys ?? new Set<string>(),
            getIconSync: host.getIconSync
        })
    );
    host.flushDOMUpdates();
    host.ui.registryScroll.scrollTop = registryScrollTop;
    return renderedWindowSignature;
};

export { renderAutomationPage };
export type { RenderHost };
