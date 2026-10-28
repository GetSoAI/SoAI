/* SoAI - Models feature OpenAI capability DOM [frontend/assets/ts/features/models/capabilities/openaiCapabilityDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveOpenAICapabilityRequirement } from '@features/models/capabilities/openaiCapabilityDependencies.ts';
import { reconcileElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { setOpenAICapabilityOverrideMode, isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken, normalizeOverrideToken, resolveOpenAICapabilityOverrideMode, type OpenAICapabilityOverrideState, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideMode } from '@features/models/capabilities/openaiCapabilityState.ts';
import { EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY } from '@features/models/modals/constants.ts';

interface OpenAICapabilityToggleRequest {
    category: OpenAICapabilityOverrideCategory;
    token: string;
    mode: OpenAICapabilityOverrideMode;
}

const parseOpenAICapabilityToggleRequest = (element: HTMLElement, state: OpenAICapabilityOverrideState): OpenAICapabilityToggleRequest => {
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
    const input = dom.resolve('input[type="checkbox"]', element);
    if (!(input instanceof HTMLInputElement)) {
        throw new TypeError('OpenAI capability override requires a checkbox');
    }
    if (!isOpenAICapabilityOverrideCategory(category)) {
        throw new Error('OpenAI capability toggle category is invalid');
    }
    if (!isSafeOpenAICapabilityToken(token)) {
        throw new Error('OpenAI capability toggle token is invalid');
    }
    const autoSupported = element.dataset['autoSupported'];
    if (autoSupported !== 'true' && autoSupported !== 'false') {
        throw new Error('OpenAI capability toggle requires its automatic state');
    }
    const originalMode = resolveOpenAICapabilityOverrideMode(state.original, category, token);
    const mode = originalMode === 'auto' && input.checked === (autoSupported === 'true') ? 'auto' : input.checked ? 'enabled' : 'disabled';
    return { category, token, mode };
};

const applyOpenAICapabilityToggleRequest = (element: HTMLElement, state: OpenAICapabilityOverrideState): void => {
    const request = parseOpenAICapabilityToggleRequest(element, state);
    const input = dom.resolve('input[type="checkbox"]', element);
    const requirement = resolveOpenAICapabilityRequirement(request.category, request.token);
    const draft = { ...state };
    if (input instanceof HTMLInputElement && input.checked && requirement) {
        const root = element.closest('.openai-capabilities-overrides');
        const parent = root ? dom.resolve(`.openai-capability-mode[data-category="${requirement.category}"][data-token="${requirement.token}"]`, root) : null;
        const parentInput = parent ? dom.resolve('input[type="checkbox"]', parent) : null;
        if (!(parent instanceof HTMLElement) || !(parentInput instanceof HTMLInputElement) || parentInput.disabled) {
            throw new Error('OpenAI capability prerequisite is unavailable');
        }
        if (!parentInput.checked) {
            const originalMode = resolveOpenAICapabilityOverrideMode(state.original, requirement.category, requirement.token);
            const mode = originalMode === 'auto' && parent.dataset['autoSupported'] === 'true' ? 'auto' : 'enabled';
            setOpenAICapabilityOverrideMode(draft, requirement.category, requirement.token, mode);
        }
    }
    setOpenAICapabilityOverrideMode(draft, request.category, request.token, request.mode);
    state.current = draft.current;
};

const reconcileOpenAICapabilityControls = (root: HTMLElement, html: TrustedHtml): void => {
    reconcileElementChildrenFromTrustedHtml({ target: root, html });
    for (const input of dom.resolveAll('input[type="checkbox"]', root)) {
        if (input instanceof HTMLInputElement) input.checked = input.hasAttribute('checked');
    }
};

const setOpenAICapabilityControlsBusy = (root: Element, busy: boolean): void => {
    const toggles = dom.resolveAll(`[data-action="${EDIT_MODEL_MODAL_ACTION_TOGGLE_OPENAI_CAPABILITY}"]`, root);
    for (const toggle of toggles) {
        if (!(toggle instanceof HTMLElement)) {
            continue;
        }
        const input = dom.resolve('input[type="checkbox"]', toggle);
        if (!(input instanceof HTMLInputElement)) {
            continue;
        }
        if (busy) {
            toggle.dataset['busy'] = 'true';
            setControlDisabledState(input, true);
            continue;
        }
        delete toggle.dataset['busy'];
        setControlDisabledState(input, toggle.dataset['toggleLocked'] === 'true' || toggle.getAttribute('aria-disabled') === 'true');
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

export { applyOpenAICapabilityToggleRequest, reconcileOpenAICapabilityControls, parseOpenAICapabilityToggleRequest, setOpenAICapabilityControlsBusy };
export type { OpenAICapabilityToggleRequest };
