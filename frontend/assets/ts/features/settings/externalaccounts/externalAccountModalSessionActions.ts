/* SoAI - External account modal action orchestration [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalSessionActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalBusyState, runModalBusyAction } from '@core/modals/modalBusyState.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import type { ModalCloseOptions } from '@core/modals/types.ts';
import type { DialogsServiceApi } from '@core/ui/modals/dialogs/service.ts';
import type { ExternalAccountModalElements } from '@features/settings/externalaccounts/externalAccountModalDom.ts';
import { persistCurrentExternalAccount } from '@features/settings/externalaccounts/externalAccountModalPersistence.ts';
import { resolveExternalAccountDescriptor, type ExternalAccountModalSessionState } from '@features/settings/externalaccounts/externalAccountModalSessionModel.ts';
import { setExternalAccountSurface } from '@features/settings/externalaccounts/externalAccountModalState.ts';
import type { ExternalAccountModalOpenOptions } from '@features/settings/externalaccounts/externalAccountModalTypes.ts';
import { runExternalAccountAction } from '@features/settings/externalaccounts/mutations.ts';
import type { ExternalAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';

interface ExternalAccountModalActionsArguments {
    modal: HTMLElement;
    state: ExternalAccountModalSessionState;
    elements: ExternalAccountModalElements;
    dialogs: DialogsServiceApi;
    options: ExternalAccountModalOpenOptions;
    close: (reason: string, options?: Omit<ModalCloseOptions, 'reason'> | undefined) => void;
    syncView: () => void;
    hasChanges: () => boolean;
    isSessionActive: () => boolean;
}

const requireExternalAccountActionType = (state: ExternalAccountModalSessionState): ExternalAccountEntry['accountType'] => {
    if (state.accountType === null) {
        throw new Error('External account action requires an account type');
    }
    return state.accountType;
};

const requireReloadedExternalAccount = (options: ExternalAccountModalOpenOptions, account: ExternalAccountEntry): ExternalAccountEntry => {
    const reloadedAccount = account.accountType === 'mail' ? options.findMailAccount(account.accountId) : options.findCalendarAccount(account.accountId);
    if (reloadedAccount === null) {
        throw new Error('External account reload did not include the active account');
    }
    return reloadedAccount;
};

const refreshCurrentExternalAccount = async (state: ExternalAccountModalSessionState, options: ExternalAccountModalOpenOptions, account: ExternalAccountEntry): Promise<void> => {
    const reloaded = await options.reload();
    if (!reloaded) {
        throw new Error('External account reload failed after action');
    }
    state.currentAccount = requireReloadedExternalAccount(options, account);
};

const reloadAfterExternalAccountDeletion = async (options: ExternalAccountModalOpenOptions, account: ExternalAccountEntry): Promise<void> => {
    const reloaded = await options.reload();
    if (!reloaded) {
        throw new Error(i18n.t('settings.externalAccounts.errors.reloadFailed'));
    }
    const deletedAccount = account.accountType === 'mail' ? options.findMailAccount(account.accountId) : options.findCalendarAccount(account.accountId);
    if (deletedAccount !== null) {
        throw new Error(i18n.t('settings.externalAccounts.errors.deleteFailed'));
    }
};

const discardExternalAccountModalIfDirty = async (inputArguments: Pick<ExternalAccountModalActionsArguments, 'state' | 'dialogs' | 'hasChanges'>): Promise<boolean> => {
    if (inputArguments.state.mode === 'launcher') {
        return true;
    }
    if (!inputArguments.hasChanges()) {
        return true;
    }
    return await showUnsavedChangesConfirmation({
        dialogs: inputArguments.dialogs,
        message: i18n.t('settings.externalAccounts.modal.discardChangesMessage'),
        confirmText: i18n.t('settings.externalAccounts.modal.discardAction')
    });
};

const performExternalAccountModalSave = async (inputArguments: Pick<ExternalAccountModalActionsArguments, 'state' | 'elements' | 'options' | 'syncView' | 'isSessionActive'>): Promise<void> => {
    if (inputArguments.state.accountType === null || inputArguments.state.mode === 'launcher') {
        throw new Error('External account modal save requires a concrete account type');
    }
    setExternalAccountSurface(inputArguments.elements.status, null, 'info');
    setExternalAccountSurface(inputArguments.elements.error, null, 'error');
    try {
        const result = await persistCurrentExternalAccount({
            host: inputArguments.options.host,
            form: inputArguments.elements.form,
            mode: inputArguments.state.mode,
            accountType: inputArguments.state.accountType,
            currentAccount: inputArguments.state.currentAccount
        });
        if (!inputArguments.isSessionActive()) {
            return;
        }
        inputArguments.state.currentAccount = result.account;
        inputArguments.state.mode = 'edit';
        await refreshCurrentExternalAccount(inputArguments.state, inputArguments.options, result.account);
        if (!inputArguments.isSessionActive()) {
            return;
        }
        inputArguments.syncView();
        inputArguments.options.host.feedback.show(result.successMessage, 'success');
        setExternalAccountSurface(inputArguments.elements.status, result.successMessage, 'success');
    } catch (error) {
        if (!inputArguments.isSessionActive()) {
            return;
        }
        const runtimeError = ensureError(error);
        inputArguments.options.host.feedback.handle(runtimeError, 'External account modal save');
        setExternalAccountSurface(inputArguments.elements.error, i18n.t('settings.externalAccounts.errors.saveFailed'), 'error');
    }
};

const requestExternalAccountModalPrimaryAction = async (inputArguments: Pick<ExternalAccountModalActionsArguments, 'state' | 'syncView' | 'isSessionActive'> & Pick<ExternalAccountModalActionsArguments, 'elements' | 'options'>): Promise<void> => {
    if (inputArguments.state.mode === 'launcher') {
        if (inputArguments.state.accountType === null) {
            throw new Error('External account launcher requires a selected account type');
        }
        inputArguments.state.currentAccount = null;
        inputArguments.state.mode = 'create';
        inputArguments.syncView();
        return;
    }
    await performExternalAccountModalSave(inputArguments);
};

const runExternalAccountModalAction = async (inputArguments: ExternalAccountModalActionsArguments, action: 'test' | 'sync' | 'oauth_connect' | 'oauth_clear' | 'delete', button: HTMLButtonElement): Promise<void> => {
    if (inputArguments.state.currentAccount === null) {
        throw new Error('External account action requires an active account');
    }
    const canProceed = await discardExternalAccountModalIfDirty(inputArguments);
    if (!canProceed) {
        return;
    }
    if (!inputArguments.isSessionActive()) {
        return;
    }
    const account = inputArguments.state.currentAccount;
    if (account === null) {
        throw new Error('External account action lost active account');
    }
    inputArguments.syncView();
    setExternalAccountSurface(inputArguments.elements.status, null, 'info');
    setExternalAccountSurface(inputArguments.elements.error, null, 'error');
    const busyState = createModalBusyState(inputArguments.modal, { loadingButton: button });
    try {
        await runModalBusyAction(busyState, async () => {
            const descriptor = resolveExternalAccountDescriptor(requireExternalAccountActionType(inputArguments.state));
            if (action === 'delete') {
                await inputArguments.options.host.confirmAndExecute(
                    `settings:delete:${descriptor.type}ExternalAccount`,
                    {
                        title: descriptor.messages.deleteConfirmTitle(),
                        message: descriptor.messages.deleteConfirmMessage(),
                        confirmText: i18n.t('common.delete'),
                        cancelText: i18n.t('common.cancel'),
                        variant: 'danger'
                    },
                    async () => {
                        await descriptor.api(inputArguments.options.host).delete(account.accountId);
                        await reloadAfterExternalAccountDeletion(inputArguments.options, account);
                    },
                    descriptor.messages.deleteSuccess(),
                    () => {
                        if (inputArguments.isSessionActive()) {
                            inputArguments.close('confirm');
                        }
                    },
                    null
                );
                return;
            }
            const successMessage = await runExternalAccountAction(inputArguments.options.host, descriptor, account.accountId, action);
            if (!inputArguments.isSessionActive()) {
                return;
            }
            if (action !== 'test') {
                await refreshCurrentExternalAccount(inputArguments.state, inputArguments.options, account);
                if (!inputArguments.isSessionActive()) {
                    return;
                }
                inputArguments.syncView();
            }
            inputArguments.options.host.feedback.show(successMessage, 'success');
            setExternalAccountSurface(inputArguments.elements.status, successMessage, 'success');
        });
    } catch (error) {
        if (!inputArguments.isSessionActive()) {
            return;
        }
        const runtimeError = ensureError(error);
        const defaultMessage = action === 'delete' ? i18n.t('settings.externalAccounts.errors.deleteFailed') : i18n.t('settings.externalAccounts.errors.actionFailed');
        inputArguments.options.host.feedback.handle(runtimeError, `External account modal ${action}`);
        setExternalAccountSurface(inputArguments.elements.error, defaultMessage, 'error');
    }
};

export { discardExternalAccountModalIfDirty, requestExternalAccountModalPrimaryAction, runExternalAccountModalAction };
