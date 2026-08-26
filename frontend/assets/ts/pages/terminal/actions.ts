/* SoAI - Terminal page actions [frontend/assets/ts/pages/terminal/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const TERMINAL_ACTION_TEXT_INCREASE = 'terminal.textIncrease';
export const TERMINAL_ACTION_TEXT_DECREASE = 'terminal.textDecrease';
export const TERMINAL_ACTION_CLEAR = 'terminal.clear';
export const TERMINAL_ACTION_FOCUS = 'terminal.focus';

export type TerminalActionId = typeof TERMINAL_ACTION_TEXT_INCREASE | typeof TERMINAL_ACTION_TEXT_DECREASE | typeof TERMINAL_ACTION_CLEAR | typeof TERMINAL_ACTION_FOCUS;

const { guard: isTerminalActionId } = createActionIdSet(TERMINAL_ACTION_TEXT_INCREASE, TERMINAL_ACTION_TEXT_DECREASE, TERMINAL_ACTION_CLEAR, TERMINAL_ACTION_FOCUS);

export { isTerminalActionId };
