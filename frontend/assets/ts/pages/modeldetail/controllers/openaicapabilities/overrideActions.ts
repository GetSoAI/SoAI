/* SoAI - Model detail page control layer OpenAI capabilities override actions [frontend/assets/ts/pages/modeldetail/controllers/openaicapabilities/overrideActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { hasOpenAICapabilityOverrideChanges, parseOpenAICapabilityToggleRequest, resetOpenAICapabilityOverrideState, setOpenAICapabilityOverrideEnabled, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ModelDetailOpenAICapabilityActionsHost extends PageResourcesOwnerHost, PageFeedbackOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
    populateDetailCards: () => void;
    notifySaveChanged: () => void;
}

const CAPABILITY_TOGGLE_RENDER_DELAY_MS = 300;

const syncCapabilityButtons = (card: Element, state: OpenAICapabilityOverrideState): void => {
    const dirty = hasOpenAICapabilityOverrideChanges(state);
    const saveButton = dom.resolve('#modeldetail-openai-capabilities-save', card);
    const resetButton = dom.resolve('#modeldetail-openai-capabilities-reset', card);
    if (saveButton instanceof HTMLButtonElement) {
        saveButton.disabled = !dirty;
        saveButton.classList.toggle('u-hidden', !dirty);
    }
    if (resetButton instanceof HTMLButtonElement) {
        resetButton.disabled = state.currentDisabled.size === 0 || dirty;
        resetButton.classList.toggle('u-hidden', dirty);
    }
};

const scheduleCapabilityRender = (host: ModelDetailOpenAICapabilityActionsHost, card: HTMLElement): void => {
    const existingTimerId = Number(card.dataset['capabilityRenderTimerId'] ?? '');
    if (Number.isFinite(existingTimerId) && existingTimerId > 0) {
        host.pageResources.clearTimer(existingTimerId);
    }
    const timerId = host.pageResources.setTimer((): void => {
        delete card.dataset['capabilityRenderTimerId'];
        host.populateDetailCards();
    }, CAPABILITY_TOGGLE_RENDER_DELAY_MS);
    if (timerId !== null) {
        card.dataset['capabilityRenderTimerId'] = String(timerId);
    }
};

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
    const request = parseOpenAICapabilityToggleRequest(element);
    setOpenAICapabilityOverrideEnabled(state, request.category, request.token, request.enabled);
    const row = element.closest('.openai-capability-row');
    if (row) {
        const currentDisabled = state.currentDisabled.get(request.category)?.has(request.token) === true;
        const originalDisabled = state.originalDisabled.get(request.category)?.has(request.token) === true;
        row.classList.toggle('modified', currentDisabled !== originalDisabled);
        row.classList.toggle('is-overridden', currentDisabled);
    }
    const card = element.closest('#modeldetail-status-capabilities');
    if (card instanceof HTMLElement) {
        syncCapabilityButtons(card, state);
        scheduleCapabilityRender(host, card);
    } else {
        host.populateDetailCards();
    }
    host.notifySaveChanged();
};

const resetModelDetailOpenAICapabilityOverrides = async (host: ModelDetailOpenAICapabilityActionsHost): Promise<void> => {
    if (!host.model || host.isVirtualModel()) {
        return;
    }
    const state = host.getOpenAICapabilityState();
    if (!state || state.currentDisabled.size === 0) {
        return;
    }
    const confirmed = await requireDialogsService().showConfirmation({
        title: i18n.t('modelDetail.confirmations.resetCapabilities'),
        message: i18n.t('modelDetail.confirmations.resetCapabilitiesMessage'),
        confirmText: i18n.t('modelDetail.confirmations.resetCapabilitiesConfirm'),
        cancelText: i18n.t('modelDetail.confirmations.cancel')
    });
    if (!confirmed) {
        return;
    }
    resetOpenAICapabilityOverrideState(state);
    host.populateDetailCards();
    host.notifySaveChanged();
};

export { resetModelDetailOpenAICapabilityOverrides, toggleModelDetailOpenAICapabilityOverride };
export type { ModelDetailOpenAICapabilityActionsHost };
