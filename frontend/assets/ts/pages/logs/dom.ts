/* SoAI - Logs page DOM contracts [frontend/assets/ts/pages/logs/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowSelect } from '@core/dom/narrowElement.ts';
import type { LogsUiRefs } from '@pages/logs/types.ts';

interface LogsDomHost {
    requireHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement;
    optionalHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement | null;
}

const requireRoot = (host: LogsDomHost): HTMLElement => host.requireHTMLElement("[data-section='logs']");
export const optionalLogsRoot = (host: LogsDomHost): HTMLElement | null => host.optionalHTMLElement("[data-section='logs']");

const requireOutputContainer = (host: LogsDomHost): HTMLElement => host.requireHTMLElement('#logs-output-container');
const requireOutput = (host: LogsDomHost): HTMLElement => host.requireHTMLElement('#logs-output');

const requireEmptyState = (host: LogsDomHost): HTMLElement => host.requireHTMLElement('#logs-empty-state');
const requireEmptyMessage = (host: LogsDomHost): HTMLElement => host.requireHTMLElement('#logs-empty-message');

const requireLogSourceSelect = (host: LogsDomHost): HTMLSelectElement => narrowSelect(host.requireHTMLElement('#log-source-select'), 'log-source-select');

const requireLineLimitSelect = (host: LogsDomHost): HTMLSelectElement => narrowSelect(host.requireHTMLElement('#log-line-limit-select'), 'log-line-limit-select');

export const requireLogsUi = (host: LogsDomHost): LogsUiRefs => {
    return {
        root: requireRoot(host),
        outputContainer: requireOutputContainer(host),
        output: requireOutput(host),
        emptyState: requireEmptyState(host),
        emptyMessage: requireEmptyMessage(host),
        sourceSelect: requireLogSourceSelect(host),
        lineLimitSelect: requireLineLimitSelect(host)
    };
};
