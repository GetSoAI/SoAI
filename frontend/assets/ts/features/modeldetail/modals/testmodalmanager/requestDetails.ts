/* SoAI - Model test modal request details [frontend/assets/ts/features/modeldetail/modals/testmodalmanager/requestDetails.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { formatRuntimeDateTimeOrEmpty } from '@core/primitives/dateTime.ts';
import type { RequestDetailElements, TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';

export const getRequestDetailElements = (context: TestModalRuntimeContext): RequestDetailElements => {
    return {
        model: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-model'), context.modalRoot),
        mode: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-mode'), context.modalRoot),
        started: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-started'), context.modalRoot),
        completed: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-completed'), context.modalRoot),
        prompt: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-prompt'), context.modalRoot),
        responseContainer: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-response'), context.modalRoot),
        responseValue: context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-response-value'), context.modalRoot)
    };
};

export const formatTimestamp = (value: number): string => {
    return formatRuntimeDateTimeOrEmpty(value, false);
};

export const clearRequestDetails = (context: TestModalRuntimeContext): void => {
    const container = context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-details'), context.modalRoot);
    if (!container) {
        return;
    }

    context.host.view.addClassName(container, 'u-hidden');
    const elements = getRequestDetailElements(context);
    if (elements.model) context.host.view.updateText(elements.model, '');
    if (elements.mode) context.host.view.updateText(elements.mode, '');
    if (elements.started) context.host.view.updateText(elements.started, '');
    if (elements.completed) context.host.view.updateText(elements.completed, '');
    if (elements.prompt) context.host.view.updateText(elements.prompt, '');
    if (elements.responseValue) context.host.view.updateText(elements.responseValue, '');
    if (elements.responseContainer) context.host.view.addClassName(elements.responseContainer, 'u-hidden');
};

export const updateRequestDetails = (context: TestModalRuntimeContext): void => {
    const container = context.host.view.optionalUI(modalUiSelector(context.modalId, 'request-details'), context.modalRoot);
    if (!container) {
        return;
    }

    const details = context.state.currentRequest;
    if (!details) {
        clearRequestDetails(context);
        return;
    }

    context.host.view.removeClassName(container, 'u-hidden');
    const elements = getRequestDetailElements(context);

    if (elements.model) context.host.view.updateText(elements.model, details.modelLabel || details.modelId);
    if (elements.mode) context.host.view.updateText(elements.mode, details.mode === 'short' ? i18n.t('modelDetail.modal.test.shortTest') : i18n.t('modelDetail.modal.test.longTest'));
    if (elements.started) context.host.view.updateText(elements.started, formatTimestamp(details.startedAt));
    if (elements.completed) context.host.view.updateText(elements.completed, details.completedAt ? formatTimestamp(details.completedAt) : i18n.t('common.notAvailableShort'));

    if (elements.prompt) {
        const promptText = details.prompt ? context.host.view.sanitizeText(details.prompt, { allowEmpty: true }) : '';
        context.host.view.updateText(elements.prompt, promptText);
    }

    if (elements.responseContainer || elements.responseValue) {
        const shouldShowResponse = details.status === 'success' && details.response.trim().length > 0;

        if (elements.responseValue) {
            const sanitizedResponse = shouldShowResponse ? context.host.view.sanitizeText(details.response, { allowEmpty: true }) : '';
            context.host.view.updateText(elements.responseValue, sanitizedResponse);
        }
        if (elements.responseContainer) {
            context.host.view.toggleClassName(elements.responseContainer, 'u-hidden', !shouldShowResponse);
        }
    }
};

export const appendResponseText = (context: TestModalRuntimeContext, value: string): void => {
    if (!value) {
        return;
    }

    if (!context.state.currentRequest) {
        return;
    }

    context.state.currentRequest.response += value;
};
