/* SoAI - Model parameter navigation markup [frontend/assets/ts/core/chat/parameters/modelParameterNavigationMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';

const CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS = 'chat-parameters:open-model-settings';

const renderModelParameterNavigationMarkup = (action: string): TrustedHtml => {
    const title = i18n.t('chat.configuration.model_settings.title');
    const buttonLabel = i18n.t('settings.title');
    const buttonTitle = i18n.t('header.actions.openSettings');
    const unavailable = i18n.t('chat.configuration.model_settings.detailUnavailable');
    return uiHtml`
        <div class="chat-configuration-section-header">
            <div class="chat-configuration-section-title">${uiText(title)}</div>
            <button type="button" class="ui-button model-settings-link" data-action="${uiAttr(action)}" aria-label="${uiAttr(buttonTitle)}" data-tooltip="${uiAttr(buttonTitle)}" disabled aria-disabled="true">${uiText(buttonLabel)}</button>
        </div>
        <span class="chat-configuration-hint" data-model-detail-unavailable>${uiText(unavailable)}</span>
    `;
};

const configureModelParameterNavigation = (modal: HTMLElement, detailUniversalId: string | null): string | null => {
    const button = dom.resolve(`[data-action="${CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS}"]`, modal);
    const unavailable = dom.resolve('[data-model-detail-unavailable]', modal);
    if (!(button instanceof HTMLButtonElement)) throw new Error('Model parameter navigation button is missing');
    if (!(unavailable instanceof HTMLElement)) throw new Error('Model parameter navigation status is missing');
    const normalized = toTrimmedString(detailUniversalId);
    setControlDisabledState(button, !normalized);
    unavailable.hidden = Boolean(normalized);
    return normalized || null;
};

export { CHAT_PARAMETER_ACTION_OPEN_MODEL_SETTINGS, configureModelParameterNavigation, renderModelParameterNavigationMarkup };
