/* SoAI - File Explorer listing status bar markup [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerStatusBarWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DirectoryListingBrowserState } from '@core/fileexplorerbrowser/types.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';

const renderFileExplorerStatusBar = (): TrustedHtml => uiHtml`<div class="file-explorer-status-bar" role="status" aria-label="${uiAttr(i18n.t('fileExplorer.aria.statusBar'))}"><span id="file-explorer-selection-status" class="ui-badge ui-badge--compact file-explorer-status-bar__badge file-explorer-status-bar__badge--selection u-hidden"><span class="file-explorer-status-bar__label">${uiText(i18n.t('fileExplorer.labels.selected'))}</span><span id="file-explorer-selection-count" class="file-explorer-status-bar__value">0</span></span><span class="ui-badge ui-badge--compact file-explorer-status-bar__badge"><span class="file-explorer-status-bar__label">${uiText(i18n.t('fileExplorer.labels.results'))}</span><span id="file-explorer-result-count" class="file-explorer-status-bar__value">---</span></span><span id="file-explorer-listing-status" class="file-explorer-status-bar__freshness" hidden></span></div>`;

const renderFileExplorerListingStatus = (ui: Pick<FileExplorerUiRefs, 'resultCount' | 'listingStatus'>, state: DirectoryListingBrowserState): void => {
    const element = ui.listingStatus;
    element.dataset['listingFreshness'] = state.freshness;
    let label: string;
    if (state.isLoading) label = state.query ? i18n.t('fileExplorer.status.searching') : i18n.t('fileExplorer.status.loading');
    else if (state.freshness === 'refreshing') label = i18n.t('fileExplorer.status.refreshing');
    else if (state.freshness === 'stale') label = i18n.t('fileExplorer.status.stale');
    else if (state.freshness === 'unavailable') label = i18n.t('fileExplorer.status.unavailable');
    else label = state.query && state.truncated ? i18n.t('fileExplorer.labels.resultsTruncated') : '';
    if (label && (state.freshness === 'stale' || state.freshness === 'unavailable') && state.updatedAtMs !== null) label = `${label} · ${formatDateTime(state.updatedAtMs, true)}`;
    ui.resultCount.textContent = state.isLoading ? i18n.t('common.loading') : `${String(state.total)}${state.query && state.truncated ? '+' : ''}`;
    element.textContent = state.errorMessage ? `${state.errorMessage} ${label}` : label;
    element.hidden = element.textContent.length === 0;
    setTooltipText(element, state.errorMessage ? `${state.errorMessage} ${label}` : label);
};

export { renderFileExplorerStatusBar, renderFileExplorerListingStatus };
