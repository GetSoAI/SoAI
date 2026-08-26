/* SoAI - Logs page clear action ownership [frontend/assets/ts/pages/logs/controllers/page/logsPageClearController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatTimeSecond } from '@core/primitives/dateTime.ts';
import type { LogStreamView } from '@features/logging/public.ts';
import { showLogsPlaceholder } from '@pages/logs/controllers/page/logsPagePlaceholderController.ts';
import type { LogsUiRefs } from '@pages/logs/types.ts';

export type LogsPageClearControllerDependencies = {
    doc: Document;
    ui: LogsUiRefs;
    output: Element | null;
    logView: LogStreamView;
    replaceElementContent: (target: Element, html: DocumentFragment, options?: { escape?: boolean }) => void;
};

export const clearLogsPage = (dependencies: LogsPageClearControllerDependencies): void => {
    dependencies.logView.reset();
    if (dependencies.output) {
        dependencies.replaceElementContent(dependencies.output, dependencies.doc.createDocumentFragment(), { escape: false });
    }
    const clearedAt = formatTimeSecond(new Date());
    showLogsPlaceholder(dependencies.ui, i18n.t('logs.clearedAt', { time: clearedAt }));
};
