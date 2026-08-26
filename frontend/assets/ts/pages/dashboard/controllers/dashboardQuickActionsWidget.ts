/* SoAI - Dashboard page quick actions widget [frontend/assets/ts/pages/dashboard/controllers/dashboardQuickActionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE } from '@pages/dashboard/actions.ts';
import type { DashboardHost, DashboardQuickActionContribution } from '@core/edition/dashboardContribution.ts';

interface DashboardQuickActionsRendererDependencies {
    host: DashboardHost;
    productActions: readonly DashboardQuickActionContribution[];
}

const QUICK_ACTION_COUNT = 20;

const QUICK_ACTION_SETTINGS: DashboardQuickActionContribution = { pageId: 'settings', icon: 'settings', getLabel: (): string => i18n.t('nav.settings') };

const QUICK_ACTION_SHARED_DEFINITIONS: readonly DashboardQuickActionContribution[] = [
    { pageId: 'settings?tab=theme', icon: 'sparkle', getLabel: (): string => i18n.t('settings.tabs.theme') },
    { pageId: 'chat', icon: 'chat', getLabel: (): string => i18n.t('nav.chat') },
    { pageId: 'automation', icon: 'automation', getLabel: (): string => i18n.t('nav.automation') },
    { pageId: 'models', icon: 'model-default', getLabel: (): string => i18n.t('nav.models') },
    { pageId: 'plugins', icon: 'plugin', getLabel: (): string => i18n.t('nav.plugins') },
    { pageId: 'prompts', icon: 'prompt', getLabel: (): string => i18n.t('nav.prompts') },
    { pageId: 'hardware', icon: 'hardware', getLabel: (): string => i18n.t('nav.hardware') },
    { pageId: 'metrics', icon: 'metrics', getLabel: (): string => i18n.t('nav.metrics') },
    { pageId: 'fileExplorer', icon: 'folder', getLabel: (): string => i18n.t('nav.fileExplorer') },
    { pageId: 'logs', icon: 'logs', getLabel: (): string => i18n.t('pages.logs.title') },
    { pageId: 'search', icon: 'search', getLabel: (): string => i18n.t('pages.search.title') },
    { pageId: 'updates', icon: 'refresh', getLabel: (): string => i18n.t('pages.updates.title') },
    { pageId: 'help', icon: 'help', getLabel: (): string => i18n.t('nav.help') },
    { pageId: 'about', icon: 'info', getLabel: (): string => i18n.t('nav.about') },
    { pageId: 'power', icon: 'power', getLabel: (): string => i18n.t('nav.power') },
    { pageId: 'terminal', icon: 'terminal', getLabel: (): string => i18n.t('nav.terminal') },
    { pageId: 'settings?tab=users', icon: 'user', getLabel: (): string => i18n.t('settings.tabs.users') }
];

const QUICK_ACTION_BASE_DEFINITIONS: readonly DashboardQuickActionContribution[] = [...QUICK_ACTION_SHARED_DEFINITIONS, { pageId: 'settings?tab=api-keys', icon: 'key', getLabel: (): string => i18n.t('settings.tabs.apiKeys') }, { pageId: 'settings?tab=backup', icon: 'file-database', getLabel: (): string => i18n.t('settings.tabs.backup') }, QUICK_ACTION_SETTINGS];

const assertQuickActionDefinitions = (definitions: readonly DashboardQuickActionContribution[]): void => {
    if (definitions.length !== QUICK_ACTION_COUNT) {
        throw new Error(`Dashboard quick actions must render exactly ${QUICK_ACTION_COUNT} actions`);
    }
    const finalAction = definitions[definitions.length - 1];
    if (!finalAction || finalAction.pageId !== QUICK_ACTION_SETTINGS.pageId) {
        throw new Error('Dashboard quick actions require Settings as the final action');
    }
    if (definitions.some((definition): boolean => definition.pageId === 'dashboard')) {
        throw new Error('Dashboard quick actions cannot include a dashboard self-navigation action');
    }
};

const resolveQuickActionDefinitions = (productActions: readonly DashboardQuickActionContribution[]): readonly DashboardQuickActionContribution[] => {
    if (productActions.length === 0) {
        return QUICK_ACTION_BASE_DEFINITIONS;
    }
    if (productActions.length !== 2) {
        throw new Error('Dashboard product contribution must define exactly two quick actions');
    }
    return [...QUICK_ACTION_SHARED_DEFINITIONS, ...productActions, QUICK_ACTION_SETTINGS];
};

const buildQuickActionButton = (definition: DashboardQuickActionContribution): TrustedHtml => {
    const label = definition.getLabel();
    const icon = renderIconSlot(getIconSync(definition.icon, { size: 18, strokeWidth: 1.7 }));
    return uiHtml`<button type="button" class="ui-button dashboard-quick-action" data-action="${uiAttr(DASHBOARD_ACTION_QUICK_ACTION_NAVIGATE)}" data-quick-action-page="${uiAttr(definition.pageId)}" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}">${icon}<span class="dashboard-quick-action-label">${label}</span></button>`;
};

const createDashboardQuickActionsSectionRenderer = (dependencies: DashboardQuickActionsRendererDependencies): (() => void) => {
    return (): void => {
        const content = dependencies.host.requireUI('quickActions-content');
        const definitions = resolveQuickActionDefinitions(dependencies.productActions);
        assertQuickActionDefinitions(definitions);
        const buttons = toTrustedUiHtml(definitions.map((definition): string => buildQuickActionButton(definition).html).join(''));
        const grid = uiHtml`<div class="dashboard-quick-actions">${buttons}</div>`;
        dependencies.host.replaceElementContent(content, grid, { escape: false });
        dependencies.host.flushDOMUpdates();
    };
};

export { createDashboardQuickActionsSectionRenderer };
export type { DashboardQuickActionsRendererDependencies };
