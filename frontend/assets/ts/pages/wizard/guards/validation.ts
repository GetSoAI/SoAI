/* SoAI - Wizard page validation [frontend/assets/ts/pages/wizard/guards/validation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isCanonicalUsernameInput } from '@core/users/username.ts';
import type { LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';

interface WizardAccountFields {
    username: string;
    password: string;
    confirmPassword: string;
}

const requireAccountInput = (form: HTMLFormElement, fieldName: string): HTMLInputElement => {
    const field = form.elements.namedItem(fieldName);
    if (!(field instanceof HTMLInputElement)) {
        throw new Error(`WizardPage: missing required account input "${fieldName}"`);
    }
    return field;
};

const readWizardAccountFields = (form: HTMLFormElement): WizardAccountFields => {
    const usernameField = requireAccountInput(form, 'username');
    const passwordField = requireAccountInput(form, 'password');
    const confirmPasswordField = requireAccountInput(form, 'password-confirm');
    return {
        username: usernameField.value,
        password: passwordField.value,
        confirmPassword: confirmPasswordField.value
    };
};

const readWizardOrganization = (form: HTMLFormElement): LicensingOrganizationInput => {
    const value = (name: string): string => requireAccountInput(form, name).value.trim();
    const authority = requireAccountInput(form, 'authority-attested');
    if (!authority.checked) throw new TypeError('Wizard organization authority attestation is required.');
    const countryCode = value('country-code').toUpperCase();
    if (!/^[A-Z]{2}$/.test(countryCode)) throw new TypeError('Wizard organization country code is invalid.');
    return {
        legalName: value('legal-name'),
        countryCode,
        registrationOrTaxId: value('registration-or-tax-id'),
        authorizedAcceptorName: value('authorized-acceptor-name'),
        authorizedAcceptorEmail: value('authorized-acceptor-email'),
        authorityAttested: true
    };
};

const isUsernameEligibleForSubmit = (username: string): boolean => {
    return isCanonicalUsernameInput(username);
};

const isPasswordEligibleForSubmit = (password: string, confirmPassword: string): boolean => {
    if (password.length < 8) {
        return false;
    }
    if (confirmPassword.length === 0) {
        return false;
    }
    return password === confirmPassword;
};

const isWizardAccountFormEligibleForSubmit = (form: HTMLFormElement): boolean => {
    const fields = readWizardAccountFields(form);
    if (!isUsernameEligibleForSubmit(fields.username)) {
        return false;
    }
    return isPasswordEligibleForSubmit(fields.password, fields.confirmPassword);
};

export { isWizardAccountFormEligibleForSubmit, readWizardAccountFields, readWizardOrganization };
export type { WizardAccountFields };
