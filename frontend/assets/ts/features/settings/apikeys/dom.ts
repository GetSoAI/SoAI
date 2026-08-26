/* SoAI - Settings feature apikeys DOM contracts [frontend/assets/ts/features/settings/apikeys/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowHTMLElement, narrowInput, optionalButton, optionalHTMLElement } from '@core/dom/narrowElement.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { API_KEYS_QUOTA_MODAL_ID } from '@features/settings/apikeys/constants.ts';
import type { ApiKeysDomResolverHost } from '@features/settings/apikeys/types.ts';

const API_KEY_ITEM_SELECTOR = '.settings-record-item[data-key-id]';
const API_KEY_STATUS_BADGE_SELECTOR = '.settings-record-badge';
const API_KEY_QUOTA_MODE_BADGE_SELECTOR = '.api-key-quota-mode-badge';
const API_KEY_QUOTA_SUMMARY_SELECTOR = '.api-key-quota-summary';
const API_KEY_INFO_SELECTOR = '.api-key-info';
const API_KEY_ACTIONS_SELECTOR = '.api-key-actions';
const API_KEY_QUOTA_MODAL_STATUS_SELECTOR = '.api-key-quota-modal-status';

const requireElement = (host: ApiKeysDomResolverHost, selector: string, context?: Element): Element => host.pageDom.require(selector, context);

const requireHTMLElement = (host: ApiKeysDomResolverHost, selector: string, context?: Element): HTMLElement => host.pageDom.requireHTMLElement(selector, context);

const requireButton = (host: ApiKeysDomResolverHost, selector: string, context?: Element): HTMLButtonElement => narrowButton(host.pageDom.require(selector, context), `API keys element "${selector}"`);

const optionalApiKeyButton = (id: string, context: Element): HTMLButtonElement | null => optionalButton(dom.resolve(`#${id}`, context), `API keys element "${id}"`);

const requireCheckbox = (host: ApiKeysDomResolverHost, selector: string, context?: Element): HTMLInputElement => {
    const input = narrowInput(host.pageDom.require(selector, context), `API keys element "${selector}"`);
    if (input.type !== 'checkbox') {
        throw new TypeError(`API keys element "${selector}" must be a checkbox`);
    }
    return input;
};

const requireActionKeyId = (actionElement: HTMLElement): string => {
    return requireTrimmedDataAttribute(actionElement, 'key-id', 'API keys action');
};

const listApiKeyItems = (root: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(API_KEY_ITEM_SELECTOR, root).map((element) => narrowHTMLElement(element, API_KEY_ITEM_SELECTOR));
};

const findApiKeyQuotaSummaryElement = (apiKeyItem: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_QUOTA_SUMMARY_SELECTOR, apiKeyItem);
    return optionalHTMLElement(element, API_KEY_QUOTA_SUMMARY_SELECTOR);
};

const findApiKeyQuotaModeBadgeElement = (apiKeyItem: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_QUOTA_MODE_BADGE_SELECTOR, apiKeyItem);
    return optionalHTMLElement(element, API_KEY_QUOTA_MODE_BADGE_SELECTOR);
};

const findApiKeyStatusBadgeElement = (apiKeyItem: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_STATUS_BADGE_SELECTOR, apiKeyItem);
    return optionalHTMLElement(element, API_KEY_STATUS_BADGE_SELECTOR);
};

const findApiKeyInfoElement = (apiKeyItem: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_INFO_SELECTOR, apiKeyItem);
    return optionalHTMLElement(element, API_KEY_INFO_SELECTOR);
};

const findApiKeyActionsElement = (apiKeyInfoElement: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_ACTIONS_SELECTOR, apiKeyInfoElement);
    return optionalHTMLElement(element, API_KEY_ACTIONS_SELECTOR);
};

const optionalApiKeyQuotaModal = (): HTMLElement | null => {
    const presenter = requireModalPresenter();
    if (!presenter.isOpen(API_KEYS_QUOTA_MODAL_ID)) {
        return null;
    }
    return optionalHTMLElement(presenter.requireElement(API_KEYS_QUOTA_MODAL_ID), API_KEYS_QUOTA_MODAL_ID);
};

const findApiKeyQuotaModalStatusElement = (quotaModal: HTMLElement): HTMLElement | null => {
    const element = dom.resolve(API_KEY_QUOTA_MODAL_STATUS_SELECTOR, quotaModal);
    return optionalHTMLElement(element, API_KEY_QUOTA_MODAL_STATUS_SELECTOR);
};

export { requireElement, requireHTMLElement, requireButton, optionalApiKeyButton, requireCheckbox, requireActionKeyId, listApiKeyItems, findApiKeyStatusBadgeElement, findApiKeyQuotaModeBadgeElement, findApiKeyQuotaSummaryElement, findApiKeyInfoElement, findApiKeyActionsElement, optionalApiKeyQuotaModal, findApiKeyQuotaModalStatusElement };
