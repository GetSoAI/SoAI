/* SoAI - Models feature OpenAI capability DOM [frontend/assets/ts/features/models/capabilities/openaiCapabilityDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken, normalizeOverrideToken, type OpenAICapabilityOverrideCategory } from '@features/models/capabilities/openaiCapabilityState.ts';
import { EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY } from '@features/models/modals/constants.ts';

interface OpenAICapabilityToggleRequest {
    category: OpenAICapabilityOverrideCategory;
    token: string;
    enabled: boolean;
    checkbox: HTMLInputElement;
}

const parseOpenAICapabilityToggleRequest = (element: HTMLElement): OpenAICapabilityToggleRequest => {
    if (element.dataset['toggleLocked'] === 'true' || element.getAttribute('aria-disabled') === 'true') {
        throw new Error('OpenAI capability toggle is locked');
    }
    if (element.dataset['busy'] === 'true') {
        throw new Error('OpenAI capability toggle is busy');
    }
    const categoryRaw = element.dataset['category'];
    const tokenRaw = element.dataset['token'];
    const category = isString(categoryRaw) ? categoryRaw.trim() : '';
    const token = isString(tokenRaw) ? normalizeOverrideToken(tokenRaw) : '';
    const checkbox = dom.resolve('input[type="checkbox"]', element);
    if (!(checkbox instanceof HTMLInputElement)) {
        throw new TypeError('OpenAI capability toggle requires a checkbox input');
    }
    if (!isOpenAICapabilityOverrideCategory(category)) {
        throw new Error('OpenAI capability toggle category is invalid');
    }
    if (!isSafeOpenAICapabilityToken(token)) {
        throw new Error('OpenAI capability toggle token is invalid');
    }
    return { category, token, enabled: checkbox.checked, checkbox };
};

const setOpenAICapabilityControlsBusy = (root: Element, busy: boolean): void => {
    const toggles = dom.resolveAll(`[data-action="${EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY}"]`, root);
    for (const toggle of toggles) {
        if (!(toggle instanceof HTMLElement)) {
            continue;
        }
        const checkbox = dom.resolve('input[type="checkbox"]', toggle);
        if (!(checkbox instanceof HTMLInputElement)) {
            continue;
        }
        if (busy) {
            toggle.dataset['busy'] = 'true';
            checkbox.disabled = true;
            continue;
        }
        delete toggle.dataset['busy'];
        checkbox.disabled = toggle.dataset['toggleLocked'] === 'true' || toggle.getAttribute('aria-disabled') === 'true';
    }
    const resetButtons = dom.resolveAll('[data-openai-capability-reset="true"]', root);
    for (const resetButton of resetButtons) {
        if (!(resetButton instanceof HTMLButtonElement)) {
            continue;
        }
        if (busy) {
            setBusyDisabledState(resetButton, {
                isBusy: true,
                reuseExistingToken: true,
                createToken: createBusyDisabledToken,
                spinner: 'none'
            });
            continue;
        }
        const token = getBusyDisabledToken(resetButton);
        if (token) {
            setBusyDisabledState(resetButton, { isBusy: false, token });
        }
    }
};

export { parseOpenAICapabilityToggleRequest, setOpenAICapabilityControlsBusy };
export type { OpenAICapabilityToggleRequest };
