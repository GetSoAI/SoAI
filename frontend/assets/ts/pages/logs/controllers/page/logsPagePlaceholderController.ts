/* SoAI - Logs page placeholder presentation ownership [frontend/assets/ts/pages/logs/controllers/page/logsPagePlaceholderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { LogsUiRefs } from '@pages/logs/types.ts';

export const resolveLogsPlaceholderText = (status: string): string => {
    return status === 'reconnecting' ? i18n.t('logs.reconnecting') : i18n.t('logs.connecting');
};

export const showLogsPlaceholder = (ui: LogsUiRefs, text: string): void => {
    ui.emptyMessage.textContent = text;
    ui.emptyState.classList.toggle('u-hidden', false);
};

export const hideLogsPlaceholder = (ui: LogsUiRefs): void => {
    ui.emptyState.classList.toggle('u-hidden', true);
};
