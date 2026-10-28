/* SoAI - Chat memory profile session and save ownership [frontend/assets/ts/features/chat/modals/chatMemoryProfileModalBinding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { serializeChatMemoryProfileUpdate, type ChatMemorySnapshot, type ChatMemoryProfile, type ChatMemoryProfileUpdateRequest } from '@core/api/contracts/webuiMemoryContracts.ts';
import type { WebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { dom } from '@core/dom/dom.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { APIError } from '@core/apiError.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { setFirstRunModalCompleted } from '@core/firstrun/state.ts';
import { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { requireModalPresenter, type ModalBinder } from '@core/modals/modalPresenter.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveUnitResult } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { createDedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { translateChatMemoryProfileFieldLabel } from '@features/chat/modals/markup/chatMemoryProfileModalMarkup.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { CHAT_MEMORY_PROFILE_MODAL_ID } from '@features/chat/modals/constants.ts';
import { CHAT_MEMORY_PROFILE_FIELD_NAMES, isChatMemoryProfileFieldName, readChatMemoryProfileFieldValue, writeChatMemoryProfileFieldValue, type ChatMemoryProfileFieldName } from '@features/chat/modals/chatMemoryProfileFields.ts';

const CHAT_MEMORY_UPDATED_EVENT = 'soai:chat-memory-updated';
interface ChatMemoryProfileModalDependencies {
    storage: FirstRunStateStorage;
    apiClient: ApiClientContext & { webui?: Pick<WebuiUserEndpoints, 'memory'> | undefined };
}

const bindChatMemoryProfileModal = (modal: HTMLElement, dependencies: ChatMemoryProfileModalDependencies): ModalBinder => {
    const resources = new ResourceTracker();
    const requests = new LatestRequestController();
    const sessions = new SequenceToken();
    const presenter = requireModalPresenter();
    const requireElement = (token: string): HTMLElement => {
        const element = dom.resolve(`#${modalUiId(CHAT_MEMORY_PROFILE_MODAL_ID, token)}`, modal);
        if (!(element instanceof HTMLElement)) throw new Error(`Missing profile modal element: ${token}`);
        return element;
    };
    const saveButton = requireElement('save');
    const skipButton = requireElement('skip');
    const loadError = requireElement('load-error');
    if (!(saveButton instanceof HTMLButtonElement) || !(skipButton instanceof HTMLButtonElement)) throw new Error('Profile modal actions must be buttons');
    const fields = new Map<ChatMemoryProfileFieldName, HTMLInputElement | HTMLTextAreaElement>();
    for (const element of dom.resolveAll('.chat-memory-profile-input', modal)) {
        if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) throw new Error('Invalid profile field control');
        const name = element.dataset['field'];
        if (!isChatMemoryProfileFieldName(name)) throw new Error('Invalid profile field name');
        fields.set(name, element);
    }
    const tracker = new FieldStateTracker({ getElement: (name) => (isChatMemoryProfileFieldName(name) ? (fields.get(name) ?? null) : null) });
    let snapshot: ChatMemoryProfile | null = null;
    let revision: string | null = null;
    let account: number | null = null;
    let dirty = false;
    let saving = false;
    let reviewRequired = false;
    let reviewPending = false;
    let unconfirmedSave = false;
    let unconfirmedSubmission: { payload: ChatMemoryProfileUpdateRequest; draft: ReadonlyMap<ChatMemoryProfileFieldName, string> } | null = null;
    let controller: ReturnType<typeof createSaveController> | null = null;
    const draftKey = (): string => JSON.stringify(Array.from(fields.values(), (field) => field.value));
    const isCurrent = (session: number): boolean => sessions.isActive(session) && account !== null && getAuthManager().getCurrentUser()?.id === account && presenter.isOpen(CHAT_MEMORY_PROFILE_MODAL_ID);
    const lockControls = (): (() => void) => {
        const captured = [...fields.values(), skipButton].map((control) => ({ control, token: setBusyDisabledState(control, { isBusy: true, createToken: createBusyDisabledToken, spinner: 'none' }) }));
        return () => {
            for (const { control, token } of captured) setBusyDisabledState(control, { isBusy: false, token });
        };
    };
    const applyProfile = (profile: ChatMemoryProfile, submittedDraft: ReadonlyMap<ChatMemoryProfileFieldName, string> | null = null): void => {
        for (const [name, field] of fields) if (!submittedDraft || field.value === submittedDraft.get(name)) field.value = readChatMemoryProfileFieldValue(profile, name);
        snapshot = profile;
        dirty = false;
        tracker.clearAll();
        for (const [name, field] of fields) dirty = tracker.update(name, { currentValue: field.value, originalValue: readChatMemoryProfileFieldValue(profile, name) }) || dirty;
    };
    const failures = createDedupingOperationFailureReporter({
        host: {
            showNotification,
            handleError: (error) => {
                if (!(error instanceof APIError)) errorHandler.error('MemoryProfile', 'Unexpected profile operation failure', error);
            }
        }
    });
    const failurePresentation = (error: Error) => ({ errorMessage: error instanceof APIError && error.code === 'memory_revision_changed' ? i18n.t('chat.memory.errors.revisionChanged') : i18n.t('chat.memory.profile.loadFailed'), rawMessage: true, context: 'Memory profile' });
    const load = async (): Promise<void> => {
        if (dirty || saving) return;
        const session = sessions.value;
        const unlock = lockControls();
        setAriaBusy(modal, true);
        try {
            await requests.runLatest(async (run) => {
                const api = dependencies.apiClient.webui?.memory;
                if (!api) throw new Error('Memory profile API is unavailable');
                const library = await api.list({ signal: run.signal });
                if (!run.isCurrent() || !isCurrent(session) || dirty || saving) return;
                applyProfile(library.profileForm);
                revision = library.profileRevision;
                loadError.classList.add('u-hidden');
            });
        } catch (error) {
            if (isCurrent(session)) {
                loadError.classList.remove('u-hidden');
                const failure = ensureError(error);
                failures.report(failure, failurePresentation(failure));
            }
        } finally {
            unlock();
            if (isCurrent(session)) {
                setAriaBusy(modal, false);
                controller?.notifyChanged();
            }
        }
    };
    const reviewCurrent = async (): Promise<void> => {
        if (saving || reviewPending) return;
        reviewPending = true;
        const session = sessions.value;
        const draft = draftKey();
        try {
            const api = dependencies.apiClient.webui?.memory;
            if (!api) throw new Error('Memory profile API is unavailable');
            const current = await api.list();
            if (!isCurrent(session) || saving || draftKey() !== draft) return;
            const message = CHAT_MEMORY_PROFILE_FIELD_NAMES.map((name) => `${translateChatMemoryProfileFieldLabel(name)}: ${readChatMemoryProfileFieldValue(current.profileForm, name)}`).join('\n');
            const accepted = await requireDialogsService().showConfirmation({ title: i18n.t('chat.memory.errors.revisionChanged'), message, confirmText: i18n.t('common.confirm'), cancelText: i18n.t('common.cancel') });
            if (!accepted || !isCurrent(session) || saving || draftKey() !== draft) return;
            if (unconfirmedSave) {
                const submitted = unconfirmedSubmission ? serializeChatMemoryProfileUpdate(unconfirmedSubmission.payload) : null;
                const matchesSubmitted =
                    submitted !== null &&
                    CHAT_MEMORY_PROFILE_FIELD_NAMES.every((name) => {
                        if (!(name in submitted)) return true;
                        const value = submitted[name];
                        return readChatMemoryProfileFieldValue(current.profileForm, name) === (typeof value === 'string' ? value.trim() : '');
                    });
                if (matchesSubmitted) {
                    dispatchCustomEvent(CHAT_MEMORY_UPDATED_EVENT, {});
                    applyProfile(current.profileForm, unconfirmedSubmission?.draft ?? null);
                    revision = current.profileRevision;
                    unconfirmedSave = false;
                    unconfirmedSubmission = null;
                    reviewRequired = false;
                    loadError.classList.add('u-hidden');
                    controller?.notifyChanged();
                    return;
                }
                showNotification(i18n.t('chat.memory.errors.unconfirmed'), 'warning');
                return;
            }
            revision = current.profileRevision;
            reviewRequired = false;
            loadError.classList.add('u-hidden');
            controller?.notifyChanged();
        } catch (error) {
            if (isCurrent(session)) {
                const failure = ensureError(error);
                failures.report(failure, failurePresentation(failure));
            }
        } finally {
            if (sessions.isActive(session)) reviewPending = false;
        }
    };
    const captureCloseValidity = (): (() => boolean) => {
        const session = sessions.value;
        const draft = draftKey();
        return () => isCurrent(session) && draftKey() === draft && !saving;
    };
    resources.track(attachPendingOperationCloseGuard({ modal, isPending: () => saving }));
    resources.track(attachBeforeCloseConfirmationGuard({ modal, presenter, modalId: CHAT_MEMORY_PROFILE_MODAL_ID, shouldConfirmClose: () => dirty, confirmClose: showUnsavedChangesConfirmation, captureCloseValidity }));
    const invalidateAccount = (): void => {
        sessions.invalidate();
        requests.invalidate();
        snapshot = null;
        revision = null;
        controller?.dispose();
        controller = null;
        for (const field of fields.values()) field.value = '';
        if (presenter.isOpen(CHAT_MEMORY_PROFILE_MODAL_ID)) presenter.close(CHAT_MEMORY_PROFILE_MODAL_ID, { force: true, reason: 'account-changed' });
    };
    resources.track(getAuthManager().onLogin(invalidateAccount));
    resources.track(getAuthManager().onLogout(invalidateAccount));
    resources.addEventListener(modal, 'core.modal.open', () => {
        sessions.invalidate();
        requests.invalidate();
        account = getAuthManager().getCurrentUser()?.id ?? null;
        modal.dataset['profileAccount'] = String(account);
        snapshot = null;
        revision = null;
        dirty = false;
        saving = false;
        reviewRequired = false;
        reviewPending = false;
        unconfirmedSave = false;
        unconfirmedSubmission = null;
        for (const field of fields.values()) field.value = '';
        tracker.clearAll();
        controller?.dispose();
        controller = createSaveController({
            headerContextId: `${CHAT_MEMORY_PROFILE_MODAL_ID}:chatMemoryProfile`,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Chat memory profile save',
            units: [
                {
                    id: 'chatMemoryProfile',
                    hasChanges: () => dirty,
                    isValid: () => snapshot !== null && revision !== null && !saving && !reviewRequired,
                    save: () => ({ type: 'stop' }),
                    prepare: () => {
                        const session = sessions.value;
                        const api = dependencies.apiClient.webui?.memory;
                        const capturedRevision = revision;
                        const capturedDraft = new Map(Array.from(fields, ([name, field]) => [name, field.value]));
                        const payload: ChatMemoryProfileUpdateRequest = { expectedRevision: capturedRevision ?? '' };
                        if (snapshot) for (const [name, field] of fields) if (field.value !== readChatMemoryProfileFieldValue(snapshot, name)) writeChatMemoryProfileFieldValue(payload, name, field.value);
                        return {
                            isValid: () => isCurrent(session) && capturedRevision !== null && api !== undefined && !saving,
                            save: async (): Promise<SaveUnitResult> => {
                                if (!api || !isCurrent(session)) return { type: 'stop' };
                                saving = true;
                                requests.invalidate();
                                const unlock = lockControls();
                                setAriaBusy(modal, true);
                                try {
                                    let result: ChatMemorySnapshot;
                                    try {
                                        result = await api.saveChatProfile(payload);
                                    } catch (error) {
                                        const failure = ensureError(error);
                                        if (isCurrent(session)) {
                                            reviewRequired = true;
                                            unconfirmedSave = !(failure instanceof APIError && failure.status >= 400 && failure.status < 500 && failure.code !== 'database_timeout');
                                            unconfirmedSubmission = unconfirmedSave ? { payload, draft: capturedDraft } : null;
                                            loadError.classList.remove('u-hidden');
                                            failures.report(failure, failurePresentation(failure));
                                        }
                                        return { type: 'stop' };
                                    }
                                    dispatchCustomEvent(CHAT_MEMORY_UPDATED_EVENT, {});
                                    if (!isCurrent(session)) return { type: 'stop' };
                                    try {
                                        applyProfile(result.profileForm);
                                        setFirstRunModalCompleted(dependencies.storage, 'chatMemoryProfile', wallClockMs());
                                        saving = false;
                                        setAriaBusy(modal, false);
                                        presenter.close(CHAT_MEMORY_PROFILE_MODAL_ID, { reason: 'confirm' });
                                    } catch (error) {
                                        errorHandler.error('MemoryProfile', 'Confirmed profile save presentation failed', ensureError(error));
                                        showNotification(i18n.t('chat.memory.library.savedRefreshNeeded'), 'warning');
                                    }
                                    return;
                                } finally {
                                    unlock();
                                    if (sessions.isActive(session)) {
                                        saving = false;
                                        setAriaBusy(modal, false);
                                    }
                                }
                            }
                        };
                    }
                }
            ]
        });
        controller.attach({ resolveSaveButtons: () => [saveButton], autoNotifyRoot: modal });
        loadError.classList.add('u-hidden');
        terminateHandledPromise(load());
    });
    resources.addEventListener(modal, 'core.modal.close', () => {
        sessions.invalidate();
        requests.invalidate();
        controller?.dispose();
        controller = null;
    });
    resources.addEventListener(modal, 'input', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLTextAreaElement)) return;
        const name = target.dataset['field'];
        if (!isChatMemoryProfileFieldName(name) || !snapshot || saving) return;
        tracker.update(name, { currentValue: target.value, originalValue: readChatMemoryProfileFieldValue(snapshot, name) });
        dirty = CHAT_MEMORY_PROFILE_FIELD_NAMES.some((name) => fields.get(name)?.value !== (snapshot ? readChatMemoryProfileFieldValue(snapshot, name) : ''));
        controller?.notifyChanged();
    });
    resources.addEventListener(modal, 'click', (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        if (target.closest(`#${skipButton.id}`)) {
            event.preventDefault();
            if (!saving) presenter.close(CHAT_MEMORY_PROFILE_MODAL_ID, { reason: 'skip' });
        }
        if (target.closest(`#${saveButton.id}`)) {
            event.preventDefault();
            if (controller) terminateHandledPromise(controller.requestSave());
        }
        if (target.closest(`#${modalUiId(CHAT_MEMORY_PROFILE_MODAL_ID, 'retry')}`)) {
            event.preventDefault();
            if (dirty || reviewRequired) {
                terminateHandledPromise(reviewCurrent());
                return;
            }
            terminateHandledPromise(load());
        }
    });
    return {
        dispose: () => {
            sessions.invalidate();
            requests.invalidate();
            controller?.dispose();
            terminateHandledPromise(resources.cleanup());
        }
    };
};

export { CHAT_MEMORY_UPDATED_EVENT, bindChatMemoryProfileModal };
export type { ChatMemoryProfileModalDependencies };
