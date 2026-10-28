/* SoAI - Model detail page control layer OpenAI capabilities override actions [frontend/assets/ts/pages/modeldetail/controllers/openaicapabilities/overrideActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelRecord } from '@core/types/modelTypes.ts';
import { hasOpenAICapabilityOverrides, applyOpenAICapabilityToggleRequest, resetOpenAICapabilityOverrideState, type OpenAICapabilityOverrideState } from '@features/models/public.ts';

interface ModelDetailOpenAICapabilityActionsHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
    populateDetailCards: () => void;
    notifySaveChanged: () => void;
}

const toggleModelDetailOpenAICapabilityOverride = (host: ModelDetailOpenAICapabilityActionsHost, element: HTMLElement): void => {
    if (!host.model || host.isVirtualModel()) {
        return;
    }
    if (element.dataset['toggleLocked'] === 'true' || element.getAttribute('aria-disabled') === 'true' || element.dataset['busy'] === 'true') {
        return;
    }
    const state = host.getOpenAICapabilityState();
    if (!state) {
        throw new Error('ModelDetailPage requires OpenAI capability state');
    }
    applyOpenAICapabilityToggleRequest(element, state);
    host.populateDetailCards();
    host.notifySaveChanged();
};

const resetModelDetailOpenAICapabilityOverrides = (host: ModelDetailOpenAICapabilityActionsHost): void => {
    if (!host.model || host.isVirtualModel()) {
        return;
    }
    const state = host.getOpenAICapabilityState();
    if (!state || !hasOpenAICapabilityOverrides(state.current)) {
        return;
    }
    resetOpenAICapabilityOverrideState(state);
    host.populateDetailCards();
    host.notifySaveChanged();
};

export { resetModelDetailOpenAICapabilityOverrides, toggleModelDetailOpenAICapabilityOverride };
export type { ModelDetailOpenAICapabilityActionsHost };
