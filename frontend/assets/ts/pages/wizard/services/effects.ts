/* SoAI - Wizard page services effects [frontend/assets/ts/pages/wizard/services/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardCompletionResult } from '@core/auth/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { isCanonicalUsernameInput, USERNAME_MAX_LENGTH, USERNAME_MIN_LENGTH } from '@core/users/username.ts';
import { readWizardAccountFields, type WizardAccountFields } from '@pages/wizard/guards/validation.ts';
import type { WizardPageServiceHost } from '@pages/wizard/services/contracts.ts';
import type { WizardAccountUi } from '@pages/wizard/types.ts';

const isMessage = (value: string | null | undefined): value is string => isString(value) && value.trim().length > 0;

const isAccountCreated = (result: WizardCompletionResult): result is Extract<WizardCompletionResult, { status: 'authenticated' | 'sessionActivationFailed' }> => result.status === 'authenticated' || result.status === 'sessionActivationFailed';

const validateUsername = (username: string, isSubmit: boolean): string | null => {
    if (!isSubmit && username.length === 0) {
        return null;
    }
    if (username.length < USERNAME_MIN_LENGTH) {
        return i18n.t('wizard.userCreation.errors.usernameShort');
    }
    if (username.length > USERNAME_MAX_LENGTH || !isCanonicalUsernameInput(username)) {
        return i18n.t('wizard.userCreation.errors.usernameInvalid');
    }
    return null;
};

const validatePasswordLive = (password: string, confirmPassword: string): string | null => {
    const hasPassword = password.length > 0;
    const hasConfirm = confirmPassword.length > 0;
    if (!hasPassword && !hasConfirm) {
        return null;
    }
    if (hasPassword && password.length < 8) {
        return i18n.t('wizard.userCreation.errors.passwordShort');
    }
    if (hasPassword && hasConfirm && password !== confirmPassword) {
        return i18n.t('wizard.userCreation.errors.passwordMismatch');
    }
    return null;
};

const validatePasswordSubmit = (password: string, confirmPassword: string): string | null => {
    if (password.length < 8) {
        return i18n.t('wizard.userCreation.errors.passwordShort');
    }
    if (confirmPassword.length === 0 || password !== confirmPassword) {
        return i18n.t('wizard.userCreation.errors.passwordMismatch');
    }
    return null;
};

const resolveLiveValidationError = (fields: WizardAccountFields, options: { validateUsername: boolean }): string | null => {
    const passwordError = validatePasswordLive(fields.password, fields.confirmPassword);
    if (passwordError) {
        return passwordError;
    }
    if (options.validateUsername) {
        const usernameError = validateUsername(fields.username, false);
        if (usernameError) {
            return usernameError;
        }
    }
    return null;
};

const resolveSubmitValidationError = (fields: WizardAccountFields): string | null => {
    const usernameError = validateUsername(fields.username, true);
    if (usernameError) {
        return usernameError;
    }
    const passwordError = validatePasswordSubmit(fields.password, fields.confirmPassword);
    if (passwordError) {
        return passwordError;
    }
    return null;
};

const resolveAccountCreationErrorText = (result: WizardCompletionResult): string => {
    const errorMessage = 'error' in result ? result.error : null;
    if (!isMessage(errorMessage)) {
        return i18n.t('wizard.userCreation.errors.generic');
    }
    return errorMessage;
};

const handleWizardAccountSubmission = async (host: WizardPageServiceHost, account: WizardAccountUi): Promise<boolean> => {
    const ui = host.view.requireUi();
    const fields = readWizardAccountFields(account.form);

    const validationError = resolveSubmitValidationError(fields);
    if (validationError) {
        host.view.updateText(account.errorBox, validationError);
        host.view.toggleHidden(account.errorBox, false);
        return false;
    }

    host.view.state.isBusy = true;
    beginLoadingButton(ui.navNextButton);
    host.view.syncNavigation(ui, 'account');
    host.view.updateText(ui.navNextButton, i18n.t('wizard.userCreation.creating'));

    try {
        const result = await host.data.submitWizardAccount(fields.username, fields.password);
        if (isAccountCreated(result) && result.user !== null) {
            host.view.state.adminUser = result.user;
            host.view.state.completedSummary = result.completion;
            host.view.state.isSessionActivationRequired = result.status === 'sessionActivationFailed';
            host.data.markWizardHasUsers();
            const notification = result.status === 'authenticated' ? i18n.t('wizard.notifications.accountCreated') : i18n.t('wizard.notifications.accountCreatedSignInRequired');
            host.completion.notify(notification, result.status === 'authenticated' ? 'success' : 'warning');
            return true;
        }

        host.view.updateText(account.errorBox, resolveAccountCreationErrorText(result));
        host.view.toggleHidden(account.errorBox, false);
        return false;
    } catch (error) {
        const runtimeError = ensureError(error);
        host.completion.logError('Failed to create admin user', runtimeError);
        host.view.updateText(account.errorBox, i18n.t('wizard.userCreation.errors.generic'));
        host.view.toggleHidden(account.errorBox, false);
        throw runtimeError;
    } finally {
        host.view.state.isBusy = false;
        clearLoadingButtonIfNeeded(ui.navNextButton);
        host.view.updateText(ui.navNextButton, i18n.t('wizard.navigation.createAccount'));
        host.view.syncNavigation(ui, 'account');
    }
};

const handleWizardAccountInput = (host: WizardPageServiceHost, account: WizardAccountUi, options: { validateUsername: boolean }): void => {
    const fields = readWizardAccountFields(account.form);
    const validationError = resolveLiveValidationError(fields, options);
    if (!validationError) {
        host.view.toggleHidden(account.errorBox, true);
        return;
    }
    host.view.updateText(account.errorBox, validationError);
    host.view.toggleHidden(account.errorBox, false);
};

export { handleWizardAccountInput, handleWizardAccountSubmission };
