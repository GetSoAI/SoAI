/* SoAI - Chat feature memory profile modal binding [frontend/assets/ts/features/chat/modals/chatMemoryProfileModalBinding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ChatMemoryProfile, ChatMemoryProfileUpdateRequest } from '@core/api/contracts/webuiMemoryContracts.ts';
import type { WebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';
import { dom } from '@core/dom/dom.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { setFirstRunModalCompleted } from '@core/firstrun/state.ts';
import { requireModalPresenter, type ModalBinder } from '@core/modals/modalPresenter.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { CHAT_MEMORY_PROFILE_MODAL_ID } from '@features/chat/modals/constants.ts';
import { isChatMemoryProfileFieldName, readChatMemoryProfileFieldValue, writeChatMemoryProfileFieldValue } from '@features/chat/modals/chatMemoryProfileFields.ts';

const CHAT_MEMORY_UPDATED_EVENT = 'soai:chat-memory-updated';
const MODULE_ID = 'ChatMemoryProfileModal';

interface ChatMemoryProfileModalDependencies {
    storage: FirstRunStateStorage;
    apiClient: ApiClientContext & { webui?: Pick<WebuiUserEndpoints, 'memory'> | undefined };
}

const resolveMemoryApi = (apiClient: ChatMemoryProfileModalDependencies['apiClient']): WebuiUserEndpoints['memory'] | null => {
    return apiClient.webui?.memory ?? null;
};

const createEmptyProfileUpdate = (): ChatMemoryProfileUpdateRequest => ({ preferredName: '', assistantName: '', roleBackground: '', currentGoals: '', preferences: '', dislikesToAvoid: '', communicationStyle: '', recurringToolsProjects: '', extraNotes: '' });

const bindChatMemoryProfileModal = (modal: HTMLElement, dependencies: ChatMemoryProfileModalDependencies): ModalBinder => {
    const abortController = new AbortController();
    const { signal } = abortController;
    const presenter = requireModalPresenter();
    let loadVersion = 0;
    let hasLocalEdits = false;
    let baselinePayloadKey = '';
    let saveController: ReturnType<typeof createSaveController> | null = null;
    const requireActionButton = (token: string): HTMLButtonElement => {
        const selector = `#${modalUiId(CHAT_MEMORY_PROFILE_MODAL_ID, token)}`;
        const candidate = dom.resolve(selector, modal);
        if (!(candidate instanceof HTMLButtonElement)) {
            throw new Error(`Chat memory profile modal action button is missing: ${token}`);
        }
        return candidate;
    };
    const skipButton = requireActionButton('skip');
    const saveButton = requireActionButton('save');
    const setFieldValues = (profile: ChatMemoryProfile): void => {
        dom.resolveAll('.chat-memory-profile-input', modal).forEach((element) => {
            if (!(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLInputElement)) {
                return;
            }
            const fieldName = element.dataset['field'] ?? '';
            if (!isChatMemoryProfileFieldName(fieldName)) {
                throw new Error(`Unsupported chat memory profile field: ${fieldName}`);
            }
            element.value = readChatMemoryProfileFieldValue(profile, fieldName);
        });
    };
    const collectPayload = (): ChatMemoryProfileUpdateRequest => {
        const payload = createEmptyProfileUpdate();
        dom.resolveAll('.chat-memory-profile-input', modal).forEach((element) => {
            if (!(element instanceof HTMLTextAreaElement) && !(element instanceof HTMLInputElement)) {
                return;
            }
            const fieldName = element.dataset['field'] ?? '';
            if (!isChatMemoryProfileFieldName(fieldName)) {
                throw new Error(`Unsupported chat memory profile field: ${fieldName}`);
            }
            writeChatMemoryProfileFieldValue(payload, fieldName, element.value);
        });
        return payload;
    };
    const serializePayload = (payload: ChatMemoryProfileUpdateRequest): string => JSON.stringify(payload);
    const hasChanges = (): boolean => serializePayload(collectPayload()) !== baselinePayloadKey;
    const loadExistingProfile = async (requestVersion: number): Promise<void> => {
        const memoryApi = resolveMemoryApi(dependencies.apiClient);
        if (!memoryApi?.get) {
            throw new Error('Chat memory profile modal requires apiClient.webui.memory.get');
        }
        const snapshot = await memoryApi.get();
        if (signal.aborted || requestVersion !== loadVersion || hasLocalEdits) {
            return;
        }
        setFieldValues(snapshot.profileForm);
        hasLocalEdits = false;
        baselinePayloadKey = serializePayload(collectPayload());
        saveController?.notifyChanged();
    };
    const runLoadExistingProfile = async (requestVersion: number): Promise<void> => {
        try {
            await loadExistingProfile(requestVersion);
        } catch (error) {
            errorHandler.error(MODULE_ID, 'Failed to load chat memory profile snapshot', ensureError(error));
        }
    };
    const saveProfile = async (): Promise<void> => {
        if (!hasChanges()) {
            return;
        }
        const memoryApi = resolveMemoryApi(dependencies.apiClient);
        if (!memoryApi?.saveChatProfile) {
            throw new Error('Chat memory profile modal requires apiClient.webui.memory.saveChatProfile');
        }
        const payload = collectPayload();
        await memoryApi.saveChatProfile(payload);
        baselinePayloadKey = serializePayload(payload);
        hasLocalEdits = false;
        setFirstRunModalCompleted(dependencies.storage, 'chatMemoryProfile', wallClockMs());
        dispatchCustomEvent(CHAT_MEMORY_UPDATED_EVENT, {});
        presenter.close(CHAT_MEMORY_PROFILE_MODAL_ID, { reason: 'confirm' });
    };
    let skipButtonBusyToken: BusyDisabledToken | null = null;
    const setSkipButtonBusy = (busy: boolean): void => {
        if (busy) {
            if (skipButtonBusyToken === null) {
                skipButtonBusyToken = setBusyDisabledState(skipButton, {
                    isBusy: true,
                    createToken: createBusyDisabledToken,
                    spinner: 'none'
                });
            }
            return;
        }
        if (skipButtonBusyToken !== null) {
            setBusyDisabledState(skipButton, { isBusy: false, token: skipButtonBusyToken });
            skipButtonBusyToken = null;
        }
    };
    setAriaBusy(modal, false);
    setSkipButtonBusy(false);
    const createModalSaveController = (): ReturnType<typeof createSaveController> =>
        createSaveController({
            headerContextId: `${CHAT_MEMORY_PROFILE_MODAL_ID}:chatMemoryProfile`,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Chat memory profile save',
            units: [
                {
                    id: 'chatMemoryProfile',
                    hasChanges: () => hasChanges(),
                    isValid: () => true,
                    save: async () => {
                        try {
                            await saveProfile();
                        } catch (error) {
                            const runtimeError = ensureError(error);
                            errorHandler.error(MODULE_ID, 'Failed to save chat memory profile', runtimeError);
                            throw runtimeError;
                        }
                    }
                }
            ]
        });
    const disposeModalSaveController = (): void => {
        saveController?.dispose();
        saveController = null;
        setAriaBusy(modal, false);
        setSkipButtonBusy(false);
    };
    const activateModalSaveController = (): void => {
        disposeModalSaveController();
        saveController = createModalSaveController();
        saveController.attach({
            resolveSaveButtons: () => [saveButton],
            onBusyChange: (busy: boolean) => setSkipButtonBusy(busy),
            busyRoots: [modal],
            autoNotifyRoot: modal
        });
    };
    modal.addEventListener(
        'core.modal.open',
        () => {
            loadVersion += 1;
            hasLocalEdits = false;
            baselinePayloadKey = serializePayload(collectPayload());
            activateModalSaveController();
            saveController?.notifyChanged();
            terminateHandledPromise(runLoadExistingProfile(loadVersion));
        },
        { signal }
    );
    modal.addEventListener(
        'core.modal.close',
        () => {
            loadVersion += 1;
            disposeModalSaveController();
        },
        { signal }
    );
    modal.addEventListener(
        'input',
        (event: Event): void => {
            const target = event.target;
            if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLTextAreaElement)) {
                return;
            }
            if (!target.classList.contains('chat-memory-profile-input')) {
                return;
            }
            hasLocalEdits = true;
            saveController?.notifyChanged();
        },
        { signal }
    );
    modal.addEventListener(
        'click',
        (event: Event): void => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }
            const skipTarget = target.closest(`#${modalUiId(CHAT_MEMORY_PROFILE_MODAL_ID, 'skip')}`);
            if (skipTarget instanceof HTMLButtonElement) {
                if (saveController?.isSaving()) {
                    return;
                }
                event.preventDefault();
                presenter.close(CHAT_MEMORY_PROFILE_MODAL_ID, { reason: 'skip' });
                return;
            }
            const saveTarget = target.closest(`#${modalUiId(CHAT_MEMORY_PROFILE_MODAL_ID, 'save')}`);
            if (saveTarget instanceof HTMLButtonElement) {
                event.preventDefault();
                if (!saveController) {
                    throw new Error('Chat memory profile save controller is unavailable while modal is open');
                }
                terminateHandledPromise(saveController.requestSave());
            }
        },
        { signal }
    );
    return {
        dispose: () => {
            disposeModalSaveController();
            abortController.abort();
        }
    };
};

export { CHAT_MEMORY_UPDATED_EVENT, bindChatMemoryProfileModal };
export type { ChatMemoryProfileModalDependencies };
