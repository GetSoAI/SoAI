/* SoAI - Logs page actions [frontend/assets/ts/pages/logs/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const LOGS_ACTION_TEXT_INCREASE = 'logs.textIncrease';
export const LOGS_ACTION_TEXT_DECREASE = 'logs.textDecrease';
export const LOGS_ACTION_CLEAR = 'logs.clear';
export const LOGS_ACTION_LINE_LIMIT_CHANGE = 'logs.lineLimitChange';
export const LOGS_ACTION_SOURCE_CHANGE = 'logs.sourceChange';

export type LogsClickActionId = typeof LOGS_ACTION_TEXT_INCREASE | typeof LOGS_ACTION_TEXT_DECREASE | typeof LOGS_ACTION_CLEAR;
export type LogsChangeActionId = typeof LOGS_ACTION_LINE_LIMIT_CHANGE | typeof LOGS_ACTION_SOURCE_CHANGE;
export type LogsActionId = LogsClickActionId | LogsChangeActionId;

const { guard: isLogsActionId } = createActionIdSet(LOGS_ACTION_TEXT_INCREASE, LOGS_ACTION_TEXT_DECREASE, LOGS_ACTION_CLEAR, LOGS_ACTION_LINE_LIMIT_CHANGE, LOGS_ACTION_SOURCE_CHANGE);

const { guard: isLogsClickActionId } = createActionIdSet(LOGS_ACTION_TEXT_INCREASE, LOGS_ACTION_TEXT_DECREASE, LOGS_ACTION_CLEAR);

const { guard: isLogsChangeActionId } = createActionIdSet(LOGS_ACTION_LINE_LIMIT_CHANGE, LOGS_ACTION_SOURCE_CHANGE);

export { isLogsActionId, isLogsChangeActionId, isLogsClickActionId };
