/* SoAI - Power action option confirmation [frontend/assets/ts/features/power/confirmation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';
import { requireInputElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getRestartState } from '@core/restartStateService.ts';
import { resolveRestartTargetAction } from '@core/restartTarget.ts';
import { joinUiHtml, uiAttr, uiAttributes, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import type { ActionDefinition, ActionParameters } from '@features/power/contracts.ts';
import { restartReminderText } from '@features/power/restartPresentation.ts';

interface PowerOptionFields {
    element: HTMLElement;
    validate: () => boolean;
    read: () => ActionParameters;
}

const renderPowerOptionFields = (action: ActionDefinition): PowerOptionFields => {
    const element = dom.create('fieldset', { className: 'confirmation-fields' });
    const markup = action.options.map((option) => {
        const id = `power-confirm-${option.parameter}`;
        if (option.type === 'checkbox') return uiHtml`<label class="toggle-switch"><input type="checkbox" id="${uiAttr(id)}"${uiAttributes({ checked: option.defaultValue === true })}><span class="slider"></span><span>${uiText(option.label)}</span></label>`;
        return uiHtml`<label class="confirmation-field" for="${uiAttr(id)}"><span>${uiText(option.label)}</span><input id="${uiAttr(id)}" type="number" class="form-input" required${uiAttributes({ value: option.defaultValue, min: option.min, max: option.max, step: option.step ?? 1 })}></label>`;
    });
    dom.setHTML(element, joinUiHtml(markup), { escape: false });
    const resolver = createElementResolver(element, 'Power confirmation options');
    const delay = requireInputElement(resolver, '#power-confirm-delay', 'Power delay');
    const force = action.options.some((option) => option.parameter === 'force') ? requireInputElement(resolver, '#power-confirm-force', 'Power force') : null;
    return {
        element,
        validate: () => delay.reportValidity(),
        read: () => ({ delay: delay.valueAsNumber, ...(force ? { force: force.checked } : {}) })
    };
};

const confirmPowerAction = async (action: ActionDefinition, submit: (parameters: ActionParameters) => Promise<void>, signal: AbortSignal): Promise<boolean> => {
    const restartState = getRestartState();
    const restartRequired = resolveRestartTargetAction(restartState) === action.key;
    const fields = restartRequired ? null : renderPowerOptionFields(action);
    const immediate: ActionParameters = { delay: 0, ...(action.options.some((option) => option.parameter === 'force') ? { force: false } : {}) };
    return await requireDialogsService().showConfirmation({
        signal,
        title: action.confirm.title,
        message: action.confirm.message,
        description: action.confirm.warning,
        advisory: restartRequired ? { text: restartReminderText(restartState.reasons), variant: 'warning' } : undefined,
        fields: fields?.element,
        variant: action.variant,
        icon: action.confirm.icon,
        confirmText: action.buttonLabel,
        onConfirm: async () => {
            if (fields && !fields.validate()) return false;
            const parameters = fields ? fields.read() : immediate;
            fields?.element.setAttribute('disabled', '');
            try {
                await submit(parameters);
                return true;
            } catch (error) {
                showOperationFailureNotification({ error: ensureError(error), rawMessage: false, showNotification: (text) => showNotification(text, 'error'), onUnhandledError: (runtimeError) => errorHandler.error('PowerConfirmation', 'Power action submission failed', runtimeError) });
                return false;
            } finally {
                fields?.element.removeAttribute('disabled');
            }
        }
    });
};

export { confirmPowerAction };
