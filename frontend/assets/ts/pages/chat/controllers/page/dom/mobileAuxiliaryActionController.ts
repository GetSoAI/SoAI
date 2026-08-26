/* SoAI - Chat page mobile auxiliary action controller [frontend/assets/ts/pages/chat/controllers/page/dom/mobileAuxiliaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { renderChatMobileAuxiliaryActionButton, resolveChatMobileAuxiliaryActionDescriptor } from '@features/chat/public.ts';
import type { ChatIconResolver, ChatPageDomHost, ChatParameters } from '@pages/chat/controllers/page/dom/contracts.ts';

const CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR = '.chat-mobile-auxiliary-action-slot';

const isConfigurationToggleActive = (host: ChatPageDomHost): boolean => {
    for (const candidate of host.pageDom.query('.configuration-toggle-btn:not(.chat-mobile-auxiliary-action)')) {
        if (candidate.classList.contains('is-active')) {
            return true;
        }
    }
    return false;
};

const renderMobileAuxiliaryAction = (host: ChatPageDomHost, parameters: ChatParameters, getIcon: ChatIconResolver): void => {
    const slot = host.pageDom.optionalHTMLElement(CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR);
    if (slot === null) {
        throw new Error('Chat mobile auxiliary action slot is required');
    }
    const action = normalizeChatMobileAuxiliaryAction(parameters.inputActionMobileAuxiliaryAction);
    if (action === 'none') {
        if (slot.dataset['mobileAuxiliaryAction'] !== 'none' || slot.childElementCount > 0) {
            host.pageDom.updateHtml(slot, EMPTY_UI_HTML, { escape: false });
        }
        slot.dataset['mobileAuxiliaryAction'] = 'none';
        host.pageDom.toggleClass(slot, 'u-hidden', true);
        return;
    }
    if (slot.dataset['mobileAuxiliaryAction'] === action && slot.childElementCount === 1) {
        host.pageDom.toggleClass(slot, 'u-hidden', false);
        return;
    }
    const descriptor = resolveChatMobileAuxiliaryActionDescriptor(action);
    const markup = renderChatMobileAuxiliaryActionButton({
        descriptor,
        getIcon: (iconName, options) => getIcon(iconName, options)
    });
    host.pageDom.updateHtml(slot, markup, { escape: false });
    slot.dataset['mobileAuxiliaryAction'] = action;
    host.pageDom.toggleClass(slot, 'u-hidden', false);
    if (action === 'configuration' && slot.firstElementChild instanceof HTMLElement) {
        host.pageDom.toggleClass(slot.firstElementChild, 'is-active', isConfigurationToggleActive(host));
    }
};

export { CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR, renderMobileAuxiliaryAction };
