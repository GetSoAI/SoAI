/* SoAI - Power restart notice projection [frontend/assets/ts/features/power/restartPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireRootHTMLElement, resolveButtonList } from '@core/dom/typedElementResolver.ts';
import { i18n } from '@core/i18n/index.ts';
import type { RestartState } from '@core/restartStateGateway.ts';
import { subscribeRestartState } from '@core/restartStateService.ts';
import { resolveRestartTargetAction } from '@core/restartTarget.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const SENTENCE_END_PATTERN = /[.。．।]+$/u;

const restartReminderText = (reasons: string[]): string => {
    const reason = reasons[0];
    if (reason) {
        return i18n.t('power.restartReminder.messageWithReason', { reason });
    }
    return i18n.t('power.restartReminder.message');
};

const bindPowerModeRestartIndicator = (modal: HTMLElement, signal: AbortSignal): void => {
    const notice = requireRootHTMLElement(modal, '#power-mode-restart-notice', 'Power restart notice');
    const text = requireRootHTMLElement(notice, '.power-mode-restart-notice-text', 'Power restart notice text');
    const actions = resolveButtonList('.power-mode-button', modal, 'Power action');
    const apply = (state: RestartState): void => {
        const target = resolveRestartTargetAction(state);
        const message = target ? restartReminderText(state.reasons).replace(SENTENCE_END_PATTERN, '') : '';
        for (const button of actions) {
            const targeted = button.getAttribute('data-action') === target;
            button.toggleAttribute('data-restart-target', targeted);
            if (targeted) button.setAttribute('aria-describedby', notice.id);
            else button.removeAttribute('aria-describedby');
        }
        dom.setText(text, message);
        setTooltipText(notice, message);
        notice.classList.toggle('u-hidden', target === null);
    };
    const unsubscribe = subscribeRestartState(apply);
    signal.addEventListener('abort', unsubscribe, { once: true });
};

export { bindPowerModeRestartIndicator, restartReminderText };
