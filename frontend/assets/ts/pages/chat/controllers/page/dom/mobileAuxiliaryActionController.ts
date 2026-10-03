/* SoAI - Chat page mobile auxiliary action controller [frontend/assets/ts/pages/chat/controllers/page/dom/mobileAuxiliaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { insertWithPresence, isPresenceExiting, removeWithPresence } from '@core/animations/presence/public.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
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
    if (action === 'new_conversation' || slot.dataset['mobileAuxiliaryAction'] === 'new_conversation') {
        const anchor = host.pageDom.optionalHTMLElement(action === 'new_conversation' ? '.model-selector--composer' : '.chat-input-actions > .chat-action-btn');
        if (!anchor) {
            throw new Error('Chat mobile auxiliary placement requires a model selector and send control');
        }
        if (slot.nextElementSibling !== anchor) anchor.before(slot);
    }
    if (action === 'none') {
        for (const child of Array.from(slot.children)) {
            if (child instanceof HTMLElement) removeWithPresence(child);
        }
        slot.dataset['mobileAuxiliaryAction'] = 'none';
        host.pageDom.toggleClass(slot, 'u-hidden', true);
        return;
    }
    const visibleChildren = Array.from(slot.children).filter((child) => !isPresenceExiting(child));
    if (slot.dataset['mobileAuxiliaryAction'] === action && visibleChildren.length === 1) {
        host.pageDom.toggleClass(slot, 'u-hidden', false);
        return;
    }
    const descriptor = resolveChatMobileAuxiliaryActionDescriptor(action);
    const markup = renderChatMobileAuxiliaryActionButton({
        descriptor,
        getIcon: (iconName, options) => getIcon(iconName, options)
    });
    const created = parseSingleRootElement({ documentRef: slot.ownerDocument, html: markup, context: slot });
    if (!created) throw new Error('Chat mobile auxiliary action requires one control');
    const existing = Array.from(slot.children).find((child) => child instanceof HTMLElement && child.getAttribute('data-action') === created.getAttribute('data-action'));
    const control = existing instanceof HTMLElement ? existing : created;
    for (const child of Array.from(slot.children)) {
        if (child instanceof HTMLElement && child !== control) removeWithPresence(child);
    }
    insertWithPresence(slot, control);
    slot.dataset['mobileAuxiliaryAction'] = action;
    host.pageDom.toggleClass(slot, 'u-hidden', false);
    if (action === 'configuration') {
        host.pageDom.toggleClass(control, 'is-active', isConfigurationToggleActive(host));
    }
};

export { CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR, renderMobileAuxiliaryAction };
