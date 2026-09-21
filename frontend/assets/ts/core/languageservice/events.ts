/* SoAI - Shared language service events [frontend/assets/ts/core/languageservice/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { EVENT_REQUEST, SERVICE_NAME, log } from '@core/languageservice/constants.ts';
import { loadLanguageFlags, loadManifest } from '@core/languageservice/effects.ts';
import { resolveStorage } from '@core/languageservice/adapters.ts';
import { resolveInitialLanguagePreference } from '@core/languageservice/state.ts';
import type { StorageInterface } from '@core/languageservice/types.ts';
import type { LanguageServiceRuntime } from '@core/languageservice/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

const resolveEventTarget = (): EventTarget | null => {
    const scope = getGlobalScope();
    const candidate = scope.window;
    if (!candidate || !isFunction(candidate.addEventListener) || !isFunction(candidate.removeEventListener)) {
        return null;
    }
    return candidate;
};

const registerStorageReadyListener = (service: LanguageServiceRuntime): void => {
    const eventTarget = resolveEventTarget();
    if (!eventTarget) {
        return;
    }
    service.resources.addEventListener(
        eventTarget,
        'soai:storage:ready',
        () => {
            const resolvedStorage = resolveStorage();
            void synchronizeLanguagePreference(service, resolvedStorage).catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.error(SERVICE_NAME, 'Failed to synchronize language preference after storage ready event', runtimeError);
            });
        },
        { passive: true }
    );
};

const registerLanguageRequestListener = (service: LanguageServiceRuntime): void => {
    const eventTarget = resolveEventTarget();
    if (!eventTarget) {
        return;
    }
    service.resources.addEventListener(
        eventTarget,
        EVENT_REQUEST,
        (event: Event) => {
            if (!(typeof CustomEvent === 'function' && event instanceof CustomEvent)) {
                return;
            }
            const detail = event.detail;
            const languageValue = isObject(detail) ? detail['language'] : null;
            if (!isString(languageValue) || !languageValue.trim()) {
                return;
            }
            const language = languageValue.trim();
            if (service.isLanguageRequestSettled(language)) {
                return;
            }
            void service.setLanguage(language).catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.error(SERVICE_NAME, `Failed to apply language change: ${language}`, runtimeError);
            });
        },
        { passive: true }
    );
};

const synchronizeLanguagePreference = async (service: LanguageServiceRuntime, store: StorageInterface | null): Promise<void> => {
    if (!store || !isFunction(store.getLanguage)) {
        return;
    }
    const stored = store.getLanguage();
    if (!stored || stored === service.currentLanguage) {
        return;
    }
    if (!service.languages.has(stored)) {
        log('warn', `Ignoring unsupported stored language preference: ${stored}`);
        return;
    }
    await service.setLanguage(stored);
};

const initializeLanguageService = async (service: LanguageServiceRuntime): Promise<void> => {
    const store = resolveStorage();
    const eventTarget = resolveEventTarget();
    if (eventTarget) {
        registerStorageReadyListener(service);
    }

    await Promise.all([loadManifest(service), loadLanguageFlags(service)]);
    await service.setLanguage(resolveInitialLanguagePreference(service, store));

    if (store?.ready) {
        try {
            await store.ready;
            await synchronizeLanguagePreference(service, store);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error(SERVICE_NAME, 'Failed to synchronize language preference once storage ready', runtimeError);
        }
    } else if (store) {
        await synchronizeLanguagePreference(service, store);
    }

    if (eventTarget) {
        registerLanguageRequestListener(service);
    }
};

export { initializeLanguageService, registerLanguageRequestListener, registerStorageReadyListener, synchronizeLanguagePreference };
