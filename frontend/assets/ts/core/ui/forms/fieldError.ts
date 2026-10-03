/* SoAI - Shared inline form field error messages [frontend/assets/ts/core/ui/forms/fieldError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';

const FIELD_ERROR_CLASS = 'form-field-error';

const renderFieldErrorMarkup = (id: string): TrustedHtml => uiHtml`<div id="${uiAttr(id)}" class="${uiAttr(FIELD_ERROR_CLASS)} u-hidden"></div>`;

const readDescribedByTokens = (control: HTMLElement): string[] => (control.getAttribute('aria-describedby') ?? '').split(/\s+/).filter((token) => token.length > 0);

const setFieldErrorMessage = (control: HTMLElement, messageElement: HTMLElement, message: string | null): void => {
    const messageId = messageElement.id;
    if (!messageId) {
        throw new Error('Field error message element requires an id');
    }
    messageElement.textContent = message ?? '';
    messageElement.classList.toggle('u-hidden', message === null);
    const describedBy = readDescribedByTokens(control).filter((token) => token !== messageId);
    if (message !== null) {
        describedBy.push(messageId);
    }
    if (describedBy.length > 0) {
        control.setAttribute('aria-describedby', describedBy.join(' '));
    } else {
        control.removeAttribute('aria-describedby');
    }
    control.setAttribute('aria-invalid', message === null ? 'false' : 'true');
};

export { renderFieldErrorMarkup, setFieldErrorMessage };
