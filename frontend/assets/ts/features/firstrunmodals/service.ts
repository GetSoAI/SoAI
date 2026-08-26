/* SoAI - First run modals feature service [frontend/assets/ts/features/firstrunmodals/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import type { FirstRunModalId, FirstRunModalRegistration, FirstRunModalService, FirstRunModalStateMap, FirstRunPageId, FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import { isFirstRunModalPending, readFirstRunModalStateMap } from '@core/firstrun/state.ts';
import { throwIfAborted } from '@core/errors/abort.ts';

const FIRST_RUN_MODALS_SERVICE_ID = 'features.firstRunModals';

interface CreateFirstRunModalsServiceDependencies {
    modalPresenter: ModalPresenterApi;
    storage: FirstRunStateStorage & { ready?: Promise<void> | undefined };
    registrations: readonly FirstRunModalRegistration[];
}

interface FirstRunModalOpenOptions extends ModalOpenOptions {
    firstRunId: FirstRunModalId;
    firstRunReason: 'auto' | 'manual';
}

const findRegistration = (registrations: readonly FirstRunModalRegistration[], id: FirstRunModalId): FirstRunModalRegistration => {
    const registration = registrations.find((entry) => entry.id === id);
    if (!registration) {
        throw new Error(`First-run modal registration is missing for "${id}"`);
    }
    return registration;
};

const createFirstRunModalsService = (dependencies: CreateFirstRunModalsServiceDependencies): FirstRunModalService => {
    let currentState: FirstRunModalStateMap = readFirstRunModalStateMap(dependencies.storage);

    const refreshState = (): FirstRunModalStateMap => {
        currentState = readFirstRunModalStateMap(dependencies.storage);
        return currentState;
    };

    const ensureStorageReady = async (): Promise<void> => {
        if (dependencies.storage.ready) {
            await dependencies.storage.ready;
        }
        refreshState();
    };

    return {
        handlePageShow: async (pageId: FirstRunPageId, options: { signal?: AbortSignal } = {}): Promise<void> => {
            throwIfAborted(options.signal);
            await ensureStorageReady();
            throwIfAborted(options.signal);
            const nextRegistration = dependencies.registrations.find((entry) => entry.pageId === pageId && isFirstRunModalPending(currentState, entry.id));
            if (!nextRegistration) {
                return;
            }
            if (dependencies.modalPresenter.isOpen(nextRegistration.modalId)) {
                return;
            }
            if (nextRegistration.prepare) {
                const prepareOptions = options.signal ? { signal: options.signal } : {};
                await nextRegistration.prepare(prepareOptions);
                throwIfAborted(options.signal);
                refreshState();
                if (!isFirstRunModalPending(currentState, nextRegistration.id)) {
                    return;
                }
                if (dependencies.modalPresenter.isOpen(nextRegistration.modalId)) {
                    return;
                }
            }
            const openOptions: FirstRunModalOpenOptions = {
                firstRunId: nextRegistration.id,
                firstRunReason: 'auto'
            };
            dependencies.modalPresenter.open(nextRegistration.modalId, openOptions);
        },
        open: async (id: FirstRunModalId, reason: 'auto' | 'manual'): Promise<void> => {
            await ensureStorageReady();
            const registration = findRegistration(dependencies.registrations, id);
            if (reason === 'manual' && !registration.allowManualOpen) {
                throw new Error(`First-run modal "${id}" does not allow manual open`);
            }
            if (dependencies.modalPresenter.isOpen(registration.modalId)) {
                return;
            }
            if (registration.prepare) {
                await registration.prepare();
                refreshState();
                if (reason === 'auto' && !isFirstRunModalPending(currentState, registration.id)) {
                    return;
                }
                if (dependencies.modalPresenter.isOpen(registration.modalId)) {
                    return;
                }
            }
            const openOptions: FirstRunModalOpenOptions = {
                firstRunId: registration.id,
                firstRunReason: reason
            };
            dependencies.modalPresenter.open(registration.modalId, openOptions);
        },
        isPending: (id: FirstRunModalId): boolean => {
            return isFirstRunModalPending(refreshState(), id);
        }
    };
};

export { FIRST_RUN_MODALS_SERVICE_ID, createFirstRunModalsService };
export type { CreateFirstRunModalsServiceDependencies };
