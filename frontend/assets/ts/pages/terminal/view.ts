/* SoAI - Terminal page rendering [frontend/assets/ts/pages/terminal/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { TERMINAL_ACTION_CLEAR, TERMINAL_ACTION_FOCUS, TERMINAL_ACTION_TEXT_DECREASE, TERMINAL_ACTION_TEXT_INCREASE } from '@pages/terminal/actions.ts';

export const renderTerminalPageView = (): string => {
    return `<div id="terminal-root" class="terminal-page page-scrollable" data-section="terminal" data-page-transition-surface="true">
            <div class="terminal-container">
                <div class="terminal-toolbar">
                    <button class="terminal-btn" id="terminal-text-increase" data-action="${TERMINAL_ACTION_TEXT_INCREASE}" type="button" ${renderLabelAttributes(i18n.t('terminal.ariaLabels.increaseTextSize'))}></button>
                    <button class="terminal-btn" id="terminal-text-decrease" data-action="${TERMINAL_ACTION_TEXT_DECREASE}" type="button" ${renderLabelAttributes(i18n.t('terminal.ariaLabels.decreaseTextSize'))}></button>
                    <button class="terminal-btn" id="terminal-clear" data-action="${TERMINAL_ACTION_CLEAR}" type="button" ${renderLabelAttributes(i18n.t('terminal.ariaLabels.clearTerminal'))}></button>
                </div>
                <div class="terminal-shell" id="terminal-shell" data-action="${TERMINAL_ACTION_FOCUS}"></div>
            </div>
        </div>`;
};

export const renderTerminalUnavailableHtml = (inputArguments: { title: string; message: string; escapeHtml: (value: string) => string }): string => {
    const titleHtml = inputArguments.escapeHtml(inputArguments.title);
    const messageHtml = inputArguments.escapeHtml(inputArguments.message);
    return `<div class="terminal-unavailable"><div class="terminal-unavailable-title">${titleHtml}</div><div class="terminal-unavailable-message">${messageHtml}</div></div>`;
};
