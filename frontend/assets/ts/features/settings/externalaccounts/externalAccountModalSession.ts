/* SoAI - Settings feature external account modal session [frontend/assets/ts/features/settings/externalaccounts/externalAccountModalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { optionalClosestElement, optionalTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { bindFormSubmit } from '@core/dom/formSubmit.ts';
import { createFormChangeSurfaceTracker } from '@core/forms/formChangeSurfaceTracker.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModalSessionContext } from '@core/modals/modalSession.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { EXTERNAL_ACCOUNT_MODAL_ACTION_BACK, EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_CALENDAR, EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_MAIL, EXTERNAL_ACCOUNT_MODAL_ACTION_DELETE, EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CLEAR, EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CONNECT, EXTERNAL_ACCOUNT_MODAL_ACTION_SAVE, EXTERNAL_ACCOUNT_MODAL_ACTION_SYNC, EXTERNAL_ACCOUNT_MODAL_ACTION_TEST, isExternalAccountModalActionId, type ExternalAccountModalActionId } from '@features/settings/externalaccounts/actionIds.ts';
import { resolveExternalAccountModalElements } from '@features/settings/externalaccounts/externalAccountModalDom.ts';
import { canBuildCurrentExternalAccountPayload } from '@features/settings/externalaccounts/externalAccountModalPersistence.ts';
import { computeExternalAccountFormSnapshot } from '@features/settings/externalaccounts/externalAccountModalState.ts';
import { discardExternalAccountModalIfDirty, requestExternalAccountModalPrimaryAction, runExternalAccountModalAction } from '@features/settings/externalaccounts/externalAccountModalSessionActions.ts';
import type { ExternalAccountModalSessionState } from '@features/settings/externalaccounts/externalAccountModalSessionModel.ts';
import { syncExternalAccountModalView } from '@features/settings/externalaccounts/externalAccountModalSessionView.ts';
import type { ExternalAccountModalOpenOptions } from '@features/settings/externalaccounts/externalAccountModalTypes.ts';
import { applyAuthVisibility } from '@features/settings/externalaccounts/formState.ts';

const validateExternalAccountModalOpenOptions = (options: ExternalAccountModalOpenOptions): void => {
    if (options.mode === 'launcher') {
        if (options.accountType !== null && options.accountType !== undefined) {
            throw new Error('External account launcher mode must not receive an account type');
        }
        if (options.account !== null && options.account !== undefined) {
            throw new Error('External account launcher mode must not receive an account');
        }
        return;
    }
    if (options.accountType === null || options.accountType === undefined) {
        throw new Error('External account editor mode requires an account type');
    }
    if (options.mode === 'create' && options.account !== null && options.account !== undefined) {
        throw new Error('External account create mode must not receive an account');
    }
    if (options.mode === 'edit' && (options.account === null || options.account === undefined)) {
        throw new Error('External account edit mode requires an account');
    }
    if (options.account && options.account.accountType !== options.accountType) {
        throw new Error('External account edit mode requires a matching account type');
    }
};

const initializeExternalAccountModalSession = (context: ModalSessionContext<void>, presenter: ModalPresenterApi, modalId: string, options: ExternalAccountModalOpenOptions): { dispose: () => void } => {
    validateExternalAccountModalOpenOptions(options);
    const { modal, signal, close } = context;
    const elements = resolveExternalAccountModalElements(modal, modalId);
    const dialogs = requireDialogsService();
    const canReturnToLauncher = options.mode === 'launcher';
    const state: ExternalAccountModalSessionState = {
        mode: options.mode,
        accountType: options.accountType ?? null,
        currentAccount: options.account ?? null,
        baselineSnapshot: ''
    };
    const changeSurfaces = createFormChangeSurfaceTracker(elements.form);
    const canBuildPayload = (): boolean => canBuildCurrentExternalAccountPayload({ form: elements.form, mode: state.mode, accountType: state.accountType, currentAccount: state.currentAccount });
    const hasChanges = (): boolean => state.mode !== 'launcher' && computeExternalAccountFormSnapshot(elements.form) !== state.baselineSnapshot;
    const canSaveCurrentState = (): boolean => state.mode !== 'launcher' && canBuildPayload();
    let operationInFlight = false;
    let sessionClosed = false;
    const isSessionActive = (): boolean => !sessionClosed;

    const runExclusiveOperation = async (operation: () => Promise<void>): Promise<void> => {
        if (operationInFlight || sessionClosed) {
            return;
        }
        operationInFlight = true;
        try {
            await operation();
        } finally {
            operationInFlight = false;
        }
    };

    const save = createSaveController({
        headerContextId: modalId,
        headerPriority: SAVE_HEADER_PRIORITY_MODAL,
        requestContextLabel: 'ExternalAccountModal save',
        units: [{ id: 'external-account', hasChanges, isValid: canSaveCurrentState, save: async () => await requestPrimaryAction() }]
    });

    const syncView = (): void => {
        if (sessionClosed) {
            return;
        }
        syncExternalAccountModalView({ state, elements, modal, save, options, canReturnToLauncher });
        changeSurfaces.captureBaseline();
    };

    const requestPrimaryAction = async (): Promise<void> => {
        await runExclusiveOperation(async () => {
            await requestExternalAccountModalPrimaryAction({ state, elements, options, syncView, isSessionActive });
        });
    };

    const runSessionAction = async (action: 'test' | 'sync' | 'oauth_connect' | 'oauth_clear' | 'delete', button: HTMLButtonElement): Promise<void> => {
        await runExclusiveOperation(async () => {
            await runExternalAccountModalAction({ modal, state, elements, dialogs, options, close, syncView, hasChanges: () => save.hasChanges(), isSessionActive }, action, button);
        });
    };

    const handleSaveButtonClick = (): void => {
        if (state.mode === 'launcher') {
            terminateHandledPromise(requestPrimaryAction());
            return;
        }
        terminateHandledPromise(save.requestSave());
    };

    const handleModalAction = (action: ExternalAccountModalActionId): void => {
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_MAIL) {
            state.accountType = state.accountType === 'mail' ? null : 'mail';
            syncView();
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_CALENDAR) {
            state.accountType = state.accountType === 'calendar' ? null : 'calendar';
            syncView();
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_BACK) {
            terminateHandledPromise(
                runExclusiveOperation(async () => {
                    if (!canReturnToLauncher || state.mode !== 'create' || state.currentAccount !== null) {
                        return;
                    }
                    if (!(await discardExternalAccountModalIfDirty({ state, dialogs, hasChanges: () => save.hasChanges() }))) {
                        return;
                    }
                    state.accountType = null;
                    state.mode = 'launcher';
                    state.currentAccount = null;
                    syncView();
                })
            );
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_DELETE) {
            terminateHandledPromise(runSessionAction('delete', elements.deleteButton));
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_TEST) {
            terminateHandledPromise(runSessionAction('test', elements.testButton));
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_SYNC) {
            terminateHandledPromise(runSessionAction('sync', elements.syncButton));
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CONNECT) {
            terminateHandledPromise(runSessionAction('oauth_connect', elements.oauthConnectButton));
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_OAUTH_CLEAR) {
            terminateHandledPromise(runSessionAction('oauth_clear', elements.oauthClearButton));
            return;
        }
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_SAVE) {
            if (state.mode === 'launcher') {
                handleSaveButtonClick();
            }
            return;
        }
        throw new Error('Unknown external account modal action');
    };

    const handleLauncherKeydown = (event: KeyboardEvent): void => {
        if (state.mode !== 'launcher') {
            return;
        }
        if (!(event.target instanceof Element)) {
            return;
        }
        const launcherOption = optionalClosestElement(event.target, '[data-action]', modal);
        if (!(launcherOption instanceof HTMLElement)) {
            return;
        }
        if (event.key !== 'Enter' && event.key !== ' ') {
            return;
        }
        const action = optionalTrimmedDataAttribute(launcherOption, 'action') ?? '';
        if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_MAIL) {
            event.preventDefault();
            state.accountType = state.accountType === 'mail' ? null : 'mail';
        } else if (action === EXTERNAL_ACCOUNT_MODAL_ACTION_CHOOSE_CALENDAR) {
            event.preventDefault();
            state.accountType = state.accountType === 'calendar' ? null : 'calendar';
        } else {
            return;
        }
        syncView();
    };

    const handleAuthTypeChange = (): void => {
        if (state.accountType === null) {
            return;
        }
        applyAuthVisibility(elements.form, state.accountType);
        changeSurfaces.sync();
        save.notifyChanged();
    };

    const handleFormChanged = (): void => {
        changeSurfaces.sync();
        save.notifyChanged();
    };

    const handleFormSubmit = (): void => {
        if (state.mode === 'launcher' || state.accountType === null) {
            return;
        }
        terminateHandledPromise(save.requestSave());
    };

    save.attach({ resolveSaveButtons: () => (state.mode === 'launcher' ? [] : [elements.saveButton]), busyRoots: [modal], autoNotifyRoot: modal });
    bindPageActionDispatcher({
        label: 'External account modal',
        root: modal,
        signal,
        isAction: isExternalAccountModalActionId,
        events: {
            click: {
                preventDefault: 'interactive',
                ignoreDisabled: true,
                mouseButton: 'primary',
                onAction: ({ action }): void => handleModalAction(action)
            }
        }
    });
    modal.addEventListener('keydown', handleLauncherKeydown, { signal });
    elements.authTypeSelect.addEventListener('change', handleAuthTypeChange, { signal });
    elements.form.addEventListener('input', handleFormChanged, { signal });
    elements.form.addEventListener('change', handleFormChanged, { signal });
    bindFormSubmit({
        root: elements.form,
        signal,
        form: elements.form,
        preventDefault: true,
        onSubmit: handleFormSubmit
    });
    const removeCloseGuard = attachBeforeCloseConfirmationGuard({
        modal,
        presenter,
        modalId,
        shouldConfirmClose: () => state.mode !== 'launcher' && save.hasChanges(),
        confirmClose: async () => await discardExternalAccountModalIfDirty({ state, dialogs, hasChanges: () => save.hasChanges() })
    });
    syncView();
    return {
        dispose: (): void => {
            sessionClosed = true;
            removeCloseGuard();
            changeSurfaces.clear();
            save.dispose();
        }
    };
};

export { initializeExternalAccountModalSession };
