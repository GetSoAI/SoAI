/* SoAI - Logs page rendering [frontend/assets/ts/pages/logs/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { GenerateStandardHeaderOptions, HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { EMPTY_UI_HTML, staticUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { LOGS_ACTION_CLEAR, LOGS_ACTION_LINE_LIMIT_CHANGE, LOGS_ACTION_SOURCE_CHANGE, LOGS_ACTION_TEXT_DECREASE, LOGS_ACTION_TEXT_INCREASE } from '@pages/logs/actions.ts';

type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;
type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;

const resolveLogLineLimitLabel = (limit: number): string => {
    switch (limit) {
        case 100:
            return i18n.t('logs.logLineLimit.options.100');
        case 250:
            return i18n.t('logs.logLineLimit.options.250');
        case 500:
            return i18n.t('logs.logLineLimit.options.500');
        case 1000:
            return i18n.t('logs.logLineLimit.options.1000');
        case 2000:
            return i18n.t('logs.logLineLimit.options.2000');
        case 5000:
            return i18n.t('logs.logLineLimit.options.5000');
        default:
            return i18n.t('common.unknown');
    }
};

const renderSourceSelect = (sources: readonly string[], selectedSource: string): TrustedHtml => {
    const options = sources
        .map((name) => {
            const label = name === 'core' ? i18n.t('logs.logSource.options.core') : name;
            return uiHtml`
                <option value="${uiAttr(name)}"${name === selectedSource ? staticUiHtml` selected` : EMPTY_UI_HTML}>${label}</option>
            `.html;
        })
        .join('');
    return uiHtml`
        <span class="dropdown-select page-header-filter-select-shell logs-source-select-shell">
        <select
            class="page-header-filter-select logs-source-select"
            id="log-source-select"
            data-action="${uiAttr(LOGS_ACTION_SOURCE_CHANGE)}"
            aria-label="${uiAttr(i18n.t('logs.ariaLabels.logSource'))}"
        >
            ${toTrustedUiHtml(options)}
        </select>
        </span>
    `;
};

const renderLineLimitSelect = (logLineLimits: readonly number[], selectedLineLimit: number): TrustedHtml => {
    const options = logLineLimits
        .map(
            (limit) =>
                uiHtml`
            <option value="${uiAttr(String(limit))}"${limit === selectedLineLimit ? staticUiHtml` selected` : EMPTY_UI_HTML}>
                ${resolveLogLineLimitLabel(limit)}
            </option>
        `.html
        )
        .join('');
    return uiHtml`
        <span class="dropdown-select page-header-filter-select-shell logs-line-limit-select-shell">
        <select
            class="page-header-filter-select logs-line-limit-select"
            id="log-line-limit-select"
            data-action="${uiAttr(LOGS_ACTION_LINE_LIMIT_CHANGE)}"
            aria-label="${uiAttr(i18n.t('logs.ariaLabels.logLineLimit'))}"
        >
            ${toTrustedUiHtml(options)}
        </select>
        </span>
    `;
};

const renderTextIncreaseButton = (getIconSync: GetIconSyncFunctionValue): TrustedHtml => uiHtml`
    <button
        type="button"
        class="ui-button ui-variant-neutral"
        id="logs-text-increase"
        data-action="${uiAttr(LOGS_ACTION_TEXT_INCREASE)}"
        aria-label="${uiAttr(i18n.t('logs.ariaLabels.increaseTextSize'))}"
        data-tooltip="${uiAttr(i18n.t('logs.ariaLabels.increaseTextSize'))}"
    >
        ${renderIconSlot(getIconSync('add', { size: 24, strokeWidth: 1.5 }))}
        <span>${i18n.t('logs.ariaLabels.increaseTextSize')}</span>
    </button>
`;

const renderTextDecreaseButton = (getIconSync: GetIconSyncFunctionValue): TrustedHtml => uiHtml`
    <button
        type="button"
        class="ui-button ui-variant-neutral"
        id="logs-text-decrease"
        data-action="${uiAttr(LOGS_ACTION_TEXT_DECREASE)}"
        aria-label="${uiAttr(i18n.t('logs.ariaLabels.decreaseTextSize'))}"
        data-tooltip="${uiAttr(i18n.t('logs.ariaLabels.decreaseTextSize'))}"
    >
        ${renderIconSlot(getIconSync('minus', { size: 24, strokeWidth: 1.5 }))}
        <span>${i18n.t('logs.ariaLabels.decreaseTextSize')}</span>
    </button>
`;

const renderClearButton = (getIconSync: GetIconSyncFunctionValue): TrustedHtml => uiHtml`
    <button
        type="button"
        class="ui-button ui-variant-danger logs-clear-button"
        id="logs-clear"
        data-action="${uiAttr(LOGS_ACTION_CLEAR)}"
        aria-label="${uiAttr(i18n.t('logs.ariaLabels.clearLogs'))}"
        data-tooltip="${uiAttr(i18n.t('logs.ariaLabels.clearLogs'))}"
    >
        ${renderIconSlot(getIconSync('clean', { size: 16, strokeWidth: 1.5 }))}
        <span>${i18n.t('logs.actions.clear')}</span>
    </button>
`;

interface LogsHeaderActionsDependencies {
    getIconSync: GetIconSyncFunctionValue;
    logLineLimits: readonly number[];
    selectedLineLimit: number;
    logSources: readonly string[];
    selectedLogSource: string;
}

const renderLogsHeaderActions = (dependencies: LogsHeaderActionsDependencies): HeaderActionDefinition[] => {
    if (!dependencies.logLineLimits.length) {
        throw new Error('Logs header controls require line limit options');
    }
    if (!dependencies.logSources.length) {
        throw new Error('Logs header controls require log source options');
    }
    const actions: HeaderActionDefinition[] = [
        {
            type: 'custom',
            html: renderSourceSelect(dependencies.logSources, dependencies.selectedLogSource)
        },
        {
            type: 'custom',
            html: renderLineLimitSelect(dependencies.logLineLimits, dependencies.selectedLineLimit)
        },
        {
            type: 'custom',
            html: renderTextIncreaseButton(dependencies.getIconSync)
        },
        {
            type: 'custom',
            html: renderTextDecreaseButton(dependencies.getIconSync)
        }
    ];
    actions.push({
        type: 'custom',
        html: renderClearButton(dependencies.getIconSync)
    });
    return actions;
};

interface LogsPageViewDependencies extends LogsHeaderActionsDependencies {
    generateStandardHeader: GenerateStandardHeaderFunctionValue;
}

export const renderLogsPageView = (dependencies: LogsPageViewDependencies): TrustedHtml => {
    const header = dependencies.generateStandardHeader({
        containerClass: 'logs-page page-scrollable',
        title: i18n.t('pages.logs.title'),
        description: i18n.t('logs.description'),
        floating: true,
        detachedHeaderMode: 'show',
        actions: renderLogsHeaderActions(dependencies),
        contentLayout: null
    });

    const content = uiHtml`
        <div id="logs-root" class="logs-root">
            <div class="logs-output-container" id="logs-output-container">
                <div class="logs-empty-state" id="logs-empty-state">
                    <div class="log-placeholder" id="logs-empty-message">${i18n.t('logs.connecting')}</div>
                </div>
                <div class="logs-output-content" id="logs-output"></div>
            </div>
        </div>
    `;
    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', content.html));
};
