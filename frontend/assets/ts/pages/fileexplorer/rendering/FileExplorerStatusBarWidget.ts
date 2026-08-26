/* SoAI - File Explorer listing status bar markup [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerStatusBarWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';

const renderFileExplorerStatusBar = (): TrustedHtml => uiHtml`<div class="file-explorer-status-bar" role="status" aria-label="${uiAttr(i18n.t('fileExplorer.aria.statusBar'))}"><span id="file-explorer-selection-status" class="ui-badge ui-badge--compact file-explorer-status-bar__badge file-explorer-status-bar__badge--selection u-hidden"><span class="file-explorer-status-bar__label">${uiText(i18n.t('fileExplorer.labels.selected'))}</span><span id="file-explorer-selection-count" class="file-explorer-status-bar__value">0</span></span><span class="ui-badge ui-badge--compact file-explorer-status-bar__badge"><span class="file-explorer-status-bar__label">${uiText(i18n.t('fileExplorer.labels.results'))}</span><span id="file-explorer-result-count" class="file-explorer-status-bar__value">---</span></span></div>`;

export { renderFileExplorerStatusBar };
