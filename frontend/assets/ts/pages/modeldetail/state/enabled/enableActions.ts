/* SoAI - Model detail page state enabled enable actions [frontend/assets/ts/pages/modeldetail/state/enabled/enableActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ModelDetailEnabledActionsHost extends PageFeedbackOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    requireModelId(): string;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    refreshModelsCollection: () => Promise<void>;
    api: {
        models: {
            updateEnabled: (id: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
        };
    };
}

const parseEnabledToggleRequest = (element: HTMLElement): { enabled: boolean; checkbox: HTMLInputElement } => {
    const checkbox = dom.resolve('input[type="checkbox"]', element);
    if (!(checkbox instanceof HTMLInputElement)) {
        throw new TypeError('Model enabled toggle requires a checkbox input');
    }
    return { enabled: checkbox.checked, checkbox };
};

const setTogglePending = (toggle: HTMLElement, checkbox: HTMLInputElement, pending: boolean): void => {
    if (pending) {
        toggle.dataset['pending'] = 'true';
        checkbox.disabled = true;
        return;
    }
    delete toggle.dataset['pending'];
    checkbox.disabled = false;
};

const toggleModelDetailEnabled = async (host: ModelDetailEnabledActionsHost, element: HTMLElement): Promise<void> => {
    await host.runWithBoundary('modelDetail:toggleEnabled', async () => {
        if (!host.model || host.isVirtualModel()) {
            return;
        }
        if (element.dataset['pending']) {
            return;
        }
        const { enabled, checkbox } = parseEnabledToggleRequest(element);
        const previousChecked = !enabled;
        try {
            setTogglePending(element, checkbox, true);
            await host.api.models.updateEnabled(host.requireModelId(), { enabled });
            if (host.model) {
                host.model.isEnabled = enabled;
                if (!enabled) {
                    host.model.isAvailable = false;
                }
            }
            try {
                await host.refreshModelsCollection();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.handleError(runtimeError, { context: 'ModelDetailPage.toggleEnabled.refreshModelsCollection' });
            }
            host.feedback.show(i18n.t('modelDetail.notifications.enabledUpdated'), 'success');
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.handleError(runtimeError, { context: 'ModelDetailPage.toggleEnabled' });
            checkbox.checked = previousChecked;
            host.feedback.show(i18n.t('modelDetail.notifications.enabledUpdateFailed'), 'error');
        } finally {
            setTogglePending(element, checkbox, false);
        }
    });
};

export { toggleModelDetailEnabled };
export type { ModelDetailEnabledActionsHost };
