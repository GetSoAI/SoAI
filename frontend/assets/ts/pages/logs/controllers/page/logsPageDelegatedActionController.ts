/* SoAI - Logs page delegated DOM action dispatch [frontend/assets/ts/pages/logs/controllers/page/logsPageDelegatedActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readPageControlSelectValue } from '@core/pagecontrols/selectController.ts';
import { readRequiredPositiveIntegerTextValue } from '@core/types/payloadNumberReaders.ts';
import { LOGS_ACTION_CLEAR, LOGS_ACTION_LINE_LIMIT_CHANGE, LOGS_ACTION_SOURCE_CHANGE, LOGS_ACTION_TEXT_DECREASE, LOGS_ACTION_TEXT_INCREASE, type LogsActionId } from '@pages/logs/actions.ts';

export type LogsPageDelegatedActionHost = {
    adjustTextSize: (delta: number) => void;
    clearLogs: () => void;
    changeLogLineLimit: (limit: number) => void;
    changeLogSource: (source: string) => void;
};

type ActionElement = HTMLElement & { dataset: DOMStringMap & { action: string } };
type ResolvedLogsAction = { action: LogsActionId; actionElement: ActionElement };
const LOGS_TEXT_ZOOM_STEP = 0.1;

export const dispatchLogsPageDelegatedAction = (host: LogsPageDelegatedActionHost, resolved: ResolvedLogsAction): void => {
    switch (resolved.action) {
        case LOGS_ACTION_TEXT_INCREASE: {
            host.adjustTextSize(LOGS_TEXT_ZOOM_STEP);
            return;
        }
        case LOGS_ACTION_TEXT_DECREASE: {
            host.adjustTextSize(-LOGS_TEXT_ZOOM_STEP);
            return;
        }
        case LOGS_ACTION_CLEAR: {
            host.clearLogs();
            return;
        }
        case LOGS_ACTION_LINE_LIMIT_CHANGE: {
            if (!(resolved.actionElement instanceof HTMLSelectElement)) {
                throw new Error('Log line limit change requires select element');
            }
            const nextValue = readRequiredPositiveIntegerTextValue(readPageControlSelectValue(resolved.actionElement), 'Log line limit must be a positive integer');
            host.changeLogLineLimit(nextValue);
            return;
        }
        case LOGS_ACTION_SOURCE_CHANGE: {
            if (!(resolved.actionElement instanceof HTMLSelectElement)) {
                throw new Error('Log source change requires select element');
            }
            host.changeLogSource(readPageControlSelectValue(resolved.actionElement));
            return;
        }
    }
};
