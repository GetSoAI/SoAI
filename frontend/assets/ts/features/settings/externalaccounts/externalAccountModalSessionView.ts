/* SoAI - Settings feature external account modal session view [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalSessionView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { SaveController } from '@core/save/public.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setVisibilityState } from '@core/ui/visibility.ts';
import { clearExternalAccountFormValues, computeExternalAccountFormSnapshot, resolveExternalAccountSummary, setExternalAccountSurface } from '@features/settings/externalaccounts/externalAccountModalState.ts';
import type { ExternalAccountModalElements } from '@features/settings/externalaccounts/externalAccountModalDom.ts';
import type { ExternalAccountModalOpenOptions } from '@features/settings/externalaccounts/externalAccountModalTypes.ts';
import type { ExternalAccountModalSessionState } from '@features/settings/externalaccounts/externalAccountModalSessionModel.ts';
import { applyAuthVisibility, applyCalendarFormState, applyMailFormState } from '@features/settings/externalaccounts/formState.ts';

interface SyncExternalAccountModalViewArguments {
    state: ExternalAccountModalSessionState;
    elements: ExternalAccountModalElements;
    modal: HTMLElement;
    save: SaveController;
    options: ExternalAccountModalOpenOptions;
    canReturnToLauncher: boolean;
}

const assertExternalAccountEditorState = (state: ExternalAccountModalSessionState): 'mail' | 'calendar' => {
    if (state.mode === 'launcher') {
        throw new Error('External account editor state is unavailable in launcher mode');
    }
    if (state.accountType === null) {
        throw new Error('External account editor state requires an account type');
    }
    if (state.mode === 'edit' && state.currentAccount === null) {
        throw new Error('External account edit mode requires an active account');
    }
    return state.accountType;
};

const resetExternalAccountModalDirtyState = (state: ExternalAccountModalSessionState, form: HTMLFormElement, save: SaveController): void => {
    state.baselineSnapshot = computeExternalAccountFormSnapshot(form);
    save.notifyChanged();
};

const syncExternalAccountModalForm = (state: ExternalAccountModalSessionState, form: HTMLFormElement, getMailAccounts: () => ReturnType<ExternalAccountModalOpenOptions['getMailAccounts']>): void => {
    const accountType = assertExternalAccountEditorState(state);
    clearExternalAccountFormValues(form);
    if (accountType === 'mail') {
        applyMailFormState(form, state.currentAccount?.accountType === 'mail' ? state.currentAccount : null);
    } else {
        applyCalendarFormState(form, state.currentAccount?.accountType === 'calendar' ? state.currentAccount : null, getMailAccounts());
    }
    applyAuthVisibility(form, accountType);
};

const resolveEditorTitle = (state: ExternalAccountModalSessionState): string => {
    const accountType = assertExternalAccountEditorState(state);
    if (accountType === 'mail') {
        if (state.mode === 'create') {
            return i18n.t('settings.externalAccounts.mail.form.createTitle');
        }
        return i18n.t('settings.externalAccounts.mail.form.editTitle');
    }
    if (state.mode === 'create') {
        return i18n.t('settings.externalAccounts.calendar.form.createTitle');
    }
    return i18n.t('settings.externalAccounts.calendar.form.editTitle');
};

const resolvePrimaryActionLabel = (state: ExternalAccountModalSessionState): string => {
    if (state.mode === 'launcher') {
        return i18n.t('settings.externalAccounts.shared.actions.add');
    }
    if (assertExternalAccountEditorState(state) === 'mail') {
        if (state.mode === 'create') {
            return i18n.t('settings.externalAccounts.mail.form.createAction');
        }
        return i18n.t('settings.externalAccounts.mail.form.saveAction');
    }
    if (state.mode === 'create') {
        return i18n.t('settings.externalAccounts.calendar.form.createAction');
    }
    return i18n.t('settings.externalAccounts.calendar.form.saveAction');
};

const syncExternalAccountModalView = (inputArguments: SyncExternalAccountModalViewArguments): void => {
    const { state, elements, modal, save, options, canReturnToLauncher } = inputArguments;
    const isLauncher = state.mode === 'launcher';
    const accountType = isLauncher ? state.accountType : assertExternalAccountEditorState(state);
    const isMail = accountType === 'mail';
    const isCalendar = accountType === 'calendar';
    const showBackButton = canReturnToLauncher && state.mode === 'create' && state.currentAccount === null;
    const showCloseButton = !showBackButton;
    setVisibilityState(elements.launcher, isLauncher, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.editor, !isLauncher, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.backButton, showBackButton, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.closeButton, showCloseButton, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.mailSection, isMail, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.calendarSection, isCalendar, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.mailOauthSection, isMail, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.calendarOauthSection, isCalendar, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.deleteButton, state.mode === 'edit' && state.currentAccount !== null, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.testButton, state.mode === 'edit' && state.currentAccount?.supportedActions.includes('test') === true, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.syncButton, state.mode === 'edit' && state.currentAccount?.supportedActions.includes('sync') === true, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.oauthConnectButton, state.mode === 'edit' && state.currentAccount?.supportedActions.includes('oauth_connect') === true, { mode: 'hiddenAttribute' });
    setVisibilityState(elements.oauthClearButton, state.mode === 'edit' && state.currentAccount?.supportedActions.includes('oauth_clear') === true, { mode: 'hiddenAttribute' });
    const oauthConnectLabel = state.currentAccount?.auth.oauth.status === 'ready' ? i18n.t('settings.externalAccounts.shared.actions.reconnectOauth') : i18n.t('settings.externalAccounts.shared.actions.connectOauth');
    const saveLabel = resolvePrimaryActionLabel(state);
    const editorTitle = isLauncher ? '' : resolveEditorTitle(state);
    const editorDescription = isLauncher ? '' : isMail ? i18n.t('settings.externalAccounts.mail.form.description') : i18n.t('settings.externalAccounts.calendar.form.description');
    elements.oauthConnectButton.textContent = oauthConnectLabel;
    elements.oauthConnectButton.setAttribute('aria-label', oauthConnectLabel);
    elements.oauthConnectButton.dataset['tooltip'] = oauthConnectLabel;
    elements.saveButton.textContent = saveLabel;
    elements.saveButton.setAttribute('aria-label', saveLabel);
    elements.saveButton.dataset['tooltip'] = saveLabel;
    if (isLauncher) {
        const launcherDisabled = state.accountType === null;
        setControlDisabledState(elements.saveButton, launcherDisabled);
    }
    elements.chooseMailOption.classList.toggle('is-selected', isLauncher && isMail);
    elements.chooseCalendarOption.classList.toggle('is-selected', isLauncher && isCalendar);
    elements.chooseMailOption.setAttribute('aria-pressed', String(isLauncher && isMail));
    elements.chooseCalendarOption.setAttribute('aria-pressed', String(isLauncher && isCalendar));
    elements.title.textContent = isLauncher ? i18n.t('settings.externalAccounts.modal.defaultTitle') : editorTitle;
    elements.editorTitle.textContent = editorTitle;
    elements.editorDescription.textContent = editorDescription;
    elements.summary.textContent = resolveExternalAccountSummary(state.currentAccount);
    setVisibilityState(elements.summary, !(isLauncher || state.currentAccount === null), { mode: 'hiddenAttribute' });
    modal.classList.toggle('external-account-modal--editing', state.mode === 'edit');
    if (isLauncher) {
        setExternalAccountSurface(elements.status, null, 'info');
        setExternalAccountSurface(elements.error, null, 'error');
        resetExternalAccountModalDirtyState(state, elements.form, save);
        return;
    }
    syncExternalAccountModalForm(state, elements.form, options.getMailAccounts);
    resetExternalAccountModalDirtyState(state, elements.form, save);
};

export { syncExternalAccountModalView };
