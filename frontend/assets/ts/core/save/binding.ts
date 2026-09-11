/* SoAI - Bind SaveScope to header and buttons [frontend/assets/ts/core/save/binding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import { connectSaveAutoNotify } from '@core/save/autoNotifyBinding.ts';
import { SAVE_HEADER_PRIORITY_PAGE } from '@core/save/constants.ts';
import type { BindSaveScopeOptions, SaveBinding, SaveRequestOutcome, SaveScope } from '@core/save/contracts.ts';
import { isFunction } from '@core/typeGuards.ts';
import { setAriaBusyForElements } from '@core/ui/controls/ariaBusy.ts';
import type { BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { beginLoadingButton, endLoadingButton } from '@core/ui/loadingbuttons/service.ts';

const ensureId = (value: string, context: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error(`${context} id must not be empty`);
    }
    return trimmed;
};

const resolveHeaderPriority = (value: number | undefined): number => {
    if (value === undefined) {
        return SAVE_HEADER_PRIORITY_PAGE;
    }
    if (!Number.isFinite(value)) {
        throw new Error('Save header priority must be finite');
    }
    return value;
};

const requireSaveButtons = (resolveSaveButtons: () => readonly HTMLButtonElement[]): readonly HTMLButtonElement[] => {
    const buttons = resolveSaveButtons();
    for (const button of buttons) {
        if (!(button instanceof HTMLButtonElement)) {
            throw new TypeError('resolveSaveButtons() must return only HTMLButtonElement instances');
        }
    }
    return buttons;
};

const normalizeAdditionalDirtyEventNames = (names: readonly string[] | undefined): readonly string[] => {
    const normalizedNames: string[] = [];
    for (const name of names ?? []) {
        const eventName = name.trim();
        if (!eventName) {
            throw new Error('Additional dirty event name must not be empty');
        }
        normalizedNames.push(eventName);
    }
    return normalizedNames;
};

const SAVE_REQUEST_DEBOUNCE_MS = 250;
const saveRequestState = new WeakMap<SaveScope, { inFlight: boolean; lastStartedAt: number; promise: Promise<SaveRequestOutcome> | null }>();

const requestSaveSafely = async (scope: SaveScope, context: string): Promise<SaveRequestOutcome> => {
    const label = context.trim() ? context.trim() : 'Save request';
    const now = Date.now();
    const state = saveRequestState.get(scope) ?? { inFlight: false, lastStartedAt: 0, promise: null };
    if (state.inFlight) {
        if (state.promise === null) throw new Error('Save request state is missing its in-flight Promise');
        return await state.promise;
    }
    if (now - state.lastStartedAt < SAVE_REQUEST_DEBOUNCE_MS) {
        return 'debounced';
    }
    state.inFlight = true;
    state.lastStartedAt = now;
    state.promise = (async (): Promise<SaveRequestOutcome> => {
        const finalize = (): void => {
            state.inFlight = false;
            state.lastStartedAt = Date.now();
            state.promise = null;
            scope.notifyChanged();
        };

        try {
            return await scope.requestSave();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('SaveScope', `${label} failed`, runtimeError);
            throw runtimeError;
        } finally {
            finalize();
        }
    })();
    saveRequestState.set(scope, state);
    scope.notifyChanged();

    return await state.promise;
};

const resetSaveHeaderActionState = (): void => {
    getHeaderActions().resetActionState('save');
};

const bindSaveScope = (options: BindSaveScopeOptions): SaveBinding => {
    const headerContextId = ensureId(options.headerContextId, 'Header save context');
    const scope = options.scope;
    const requestSave = options.requestSave;
    if (!isFunction(requestSave)) {
        throw new Error('bindSaveScope requires requestSave()');
    }
    const resolveSaveButtons = options.resolveSaveButtons;
    if (!isFunction(resolveSaveButtons)) {
        throw new Error('bindSaveScope requires resolveSaveButtons()');
    }
    const onBusyChange = options.onBusyChange;
    if (onBusyChange !== undefined && onBusyChange !== null && !isFunction(onBusyChange)) {
        throw new Error('bindSaveScope optional onBusyChange must be a function');
    }
    const additionalDirtyEventNames = normalizeAdditionalDirtyEventNames(options.additionalDirtyEventNames);
    const busyRoots = options.busyRoots ?? [];
    const headerPriority = resolveHeaderPriority(options.headerPriority);
    const headerActionController: HeaderActionController | null = options.enableHeaderAction === false ? null : createHeaderActionController({ actionId: 'save', contextId: headerContextId });
    const abort = new AbortController();
    const { signal } = abort;
    let disposed = false;
    let lastBusy: boolean | null = null;
    const boundSaveButtons = new WeakSet<HTMLButtonElement>();
    const busySaveButtonTokens = new Map<HTMLButtonElement, BusyDisabledToken>();

    const clearBusySaveButtons = (): void => {
        for (const [button, token] of busySaveButtonTokens) {
            endLoadingButton(button, token);
        }
        busySaveButtonTokens.clear();
    };

    const applyDisabledState = (button: HTMLButtonElement, disabled: boolean): void => {
        setControlDisabledState(button, disabled);
        const cls = options.buttonDisabledClassName;
        if (cls) {
            button.classList.toggle(cls, disabled);
        }
    };
    const requestButtonSave = (event: Event): void => {
        if (!(event.currentTarget instanceof HTMLButtonElement)) {
            throw new TypeError('Save button click target must be an HTMLButtonElement');
        }
        if (event.currentTarget.disabled) {
            return;
        }
        event.preventDefault();
        terminateHandledPromise(requestSave(`Button save (${headerContextId})`));
        sync();
    };

    const sync = (): void => {
        if (disposed) {
            return;
        }
        const hasChanges = scope.hasChanges();
        const canSave = (options.canRequestSave?.() ?? true) && scope.canSave();
        const saving = scope.isSaving();
        const inFlight = saveRequestState.get(scope)?.inFlight === true;
        const busy = saving || inFlight;
        const busyChanged = lastBusy !== busy;
        if (busyChanged) {
            lastBusy = busy;
            setAriaBusyForElements(busyRoots, busy);
        }
        if (onBusyChange && busyChanged) {
            onBusyChange(busy);
        }
        if (!busy) {
            clearBusySaveButtons();
        }
        const buttons = requireSaveButtons(resolveSaveButtons);
        const dirtyClassName = options.buttonDirtyClassName;
        for (const button of buttons) {
            if (!boundSaveButtons.has(button)) {
                boundSaveButtons.add(button);
                button.addEventListener('click', requestButtonSave, { signal });
            }
            if (busy) {
                if (!busySaveButtonTokens.has(button)) {
                    busySaveButtonTokens.set(button, beginLoadingButton(button));
                }
            }
            applyDisabledState(button, !canSave || busy);
            if (dirtyClassName) {
                button.classList.toggle(dirtyClassName, hasChanges);
            }
        }
        if (headerActionController) {
            const headerDisabled = !canSave || busy;
            if (!hasChanges || headerDisabled) {
                headerActionController.hide();
                return;
            }
            headerActionController.show({
                priority: headerPriority,
                onClick: () => {
                    terminateHandledPromise(requestSave('Header save'));
                    sync();
                }
            });
        }
    };

    const connectAutoNotify = (): void => {
        connectSaveAutoNotify({
            scope,
            headerContextId,
            signal,
            autoNotifyRoot: options.autoNotifyRoot,
            autoNotifyAdditionalRoots: options.autoNotifyAdditionalRoots,
            additionalDirtyEventNames,
            requestSave,
            sync
        });
    };

    sync();
    const scheduleSync = createMicrotaskScheduler(() => sync());
    const unsubscribe = scope.subscribe(() => scheduleSync());
    connectAutoNotify();

    return {
        sync,
        dispose: (): void => {
            if (disposed) {
                return;
            }
            disposed = true;
            if (lastBusy === true) {
                setAriaBusyForElements(busyRoots, false);
            }
            clearBusySaveButtons();
            abort.abort();
            unsubscribe();
            headerActionController?.dispose();
            if (onBusyChange && lastBusy === true) {
                onBusyChange(false);
            }
        }
    };
};

export { bindSaveScope, requestSaveSafely, resetSaveHeaderActionState };
