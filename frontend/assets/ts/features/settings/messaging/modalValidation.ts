/* SoAI - Messaging account editor validation presentation [frontend/assets/ts/features/settings/messaging/modalValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { setControlValidity } from '@core/dom/formValidity.ts';
import { setFieldSurfaceInvalid } from '@core/forms/fieldSurface.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';

type AdmissionField = 'label' | 'model' | 'credentials' | 'parameters' | 'authorizedSenders' | 'mcp';

type MessagingValidationPresenter = {
    touch: (target: EventTarget | null) => void;
    sync: (invalidFields: readonly string[]) => void;
};

const MODAL_ID = 'settings-messaging-account-modal';

const requireControl = <T extends HTMLElement>(modal: Element, token: string, expected: new (...parameters: never[]) => T): T => {
    const element = dom.resolve(modalUiSelector(MODAL_ID, token), modal);
    if (!(element instanceof expected)) throw new Error(`Messaging validation control is missing: ${token}`);
    return element;
};

const createMessagingValidationPresenter = (modal: HTMLElement, mode: 'create' | 'edit'): MessagingValidationPresenter => {
    const touchedFields = new Set<AdmissionField>();
    const touchedCredentials = new Set<HTMLInputElement>();
    const touchedNumbers = new Set<HTMLInputElement>();
    const parametersSummary = requireControl(modal, 'parameters-summary', HTMLInputElement);
    const mcpGroup = dom.resolve('.messaging-account-modal__mcp', modal);
    if (!(mcpGroup instanceof HTMLElement)) throw new Error('Messaging MCP validation surface is missing');

    const touch = (target: EventTarget | null): void => {
        if (!(target instanceof Element)) return;
        if (target.matches(modalUiSelector(MODAL_ID, 'label'))) touchedFields.add('label');
        if (target.matches(modalUiSelector(MODAL_ID, 'model'))) touchedFields.add('model');
        if (target.matches(modalUiSelector(MODAL_ID, 'authorized-senders'))) touchedFields.add('authorizedSenders');
        if (target.matches(modalUiSelector(MODAL_ID, 'accept-anyone'))) touchedFields.add('authorizedSenders');
        if (target.closest('.messaging-account-modal__mcp')) touchedFields.add('mcp');
        if (target instanceof HTMLInputElement && target.closest('.messaging-provider-credentials')) {
            touchedFields.add('credentials');
            touchedCredentials.add(target);
        }
        if (target instanceof HTMLInputElement && target.type === 'number') {
            touchedFields.add('parameters');
            touchedNumbers.add(target);
        }
    };

    const syncCredentials = (invalid: ReadonlySet<string>): void => {
        const platform = requireControl(modal, 'platform', HTMLSelectElement).value;
        for (const credential of dom.resolveAll(`.messaging-provider-credentials[data-platform="${platform}"] input`, modal)) {
            if (!(credential instanceof HTMLInputElement)) throw new Error('Messaging credential validation control must be an input');
            if (!touchedCredentials.has(credential)) continue;
            const populated = credential.value.trim() !== '';
            const valid = credential.checkValidity() && (mode === 'edit' || populated) && (!invalid.has('credentials') || populated);
            setControlValidity(credential, valid, '.setting-item');
        }
    };

    const sync = (invalidFields: readonly string[]): void => {
        const invalid = new Set(invalidFields);
        if (touchedFields.has('label')) setControlValidity(requireControl(modal, 'label', HTMLInputElement), !invalid.has('label'), '.setting-item');
        if (touchedFields.has('model')) setControlValidity(requireControl(modal, 'model', HTMLSelectElement), !invalid.has('model'), '.setting-item');
        if (touchedFields.has('authorizedSenders')) {
            setControlValidity(requireControl(modal, 'authorized-senders', HTMLTextAreaElement), !invalid.has('authorizedSenders'), '.setting-item');
        }
        if (touchedFields.has('credentials')) syncCredentials(invalid);
        for (const numeric of touchedNumbers) {
            setControlValidity(numeric, numeric.value === '' || numeric.checkValidity(), '.setting-change-surface');
        }
        setControlValidity(parametersSummary, !invalid.has('parameters'), '.setting-item');
        if (touchedFields.has('mcp')) setFieldSurfaceInvalid(mcpGroup, invalid.has('mcp'));
    };

    return { touch, sync };
};

export { createMessagingValidationPresenter };
export type { MessagingValidationPresenter };
