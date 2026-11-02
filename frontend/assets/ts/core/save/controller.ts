/* SoAI - Save controller (canonical page surface) [frontend/assets/ts/core/save/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresentationOwnerActive, isPresentationOwnerCurrent, isPresentationOwnerMutationAllowed } from '@core/presentationOwner.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { navigationResult } from '@core/navigationMiddleware.ts';
import { registerDirtyStateGuard } from '@core/navigationGuards.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { bindSaveScope, requestSaveSafely } from '@core/save/binding.ts';
import type { SaveBinding, SaveUnit } from '@core/save/contracts.ts';
import { createSaveScope } from '@core/save/scope.ts';

type SaveControllerAttachOptions = {
    resolveSaveButtons: () => readonly HTMLButtonElement[];
    enableHeaderAction?: boolean | undefined;
    onBusyChange?: ((busy: boolean) => void) | undefined;
    busyRoots?: readonly Element[] | undefined;
    autoNotifyRoot?: Element | null;
    autoNotifyAdditionalRoots?: readonly Element[] | undefined;
    additionalDirtyEventNames?: readonly string[] | undefined;
    buttonDisabledClassName?: string | null | undefined;
    buttonDirtyClassName?: string | null | undefined;
};

type CreateSaveControllerOptions = {
    readonly owner: PresentationOwner;
    headerContextId: string;
    headerPriority?: number | undefined;
    requestContextLabel: string;
    units: readonly SaveUnit[];
    onSaveComplete?: (() => void | Promise<void>) | undefined;
    onSaveSettled?: ((outcome: 'saved' | 'degraded' | 'stopped') => void | Promise<void>) | undefined;
    admission?: SaveAdmission | undefined;
    isCurrent?: (() => boolean) | undefined;
    isDestructionBlocked?: (() => boolean) | undefined;
};

type SaveAdmission = {
    canAcquire: () => boolean;
    acquire: () => (() => void) | null;
};

type SaveController = {
    readonly owner: PresentationOwner;
    attach: (options: SaveControllerAttachOptions) => void;
    hasChanges: () => boolean;
    canSave: () => boolean;
    isSaving: () => boolean;
    notifyChanged: () => void;
    requestSave: () => Promise<void>;
    dispose: () => void;
};

const createSaveController = (options: CreateSaveControllerOptions): SaveController => {
    if (!options) {
        throw new Error('createSaveController requires options');
    }
    if (typeof options.headerContextId !== 'string' || !options.headerContextId.trim()) {
        throw new Error('createSaveController requires a non-empty headerContextId');
    }
    if (typeof options.requestContextLabel !== 'string' || !options.requestContextLabel.trim()) {
        throw new Error('createSaveController requires a non-empty requestContextLabel');
    }
    if (!Array.isArray(options.units)) {
        throw new Error('createSaveController requires units[]');
    }
    const owner = options.owner;
    const scope = createSaveScope({ isCurrent: () => !disposed && isPresentationOwnerCurrent(owner) && (options.isCurrent?.() ?? true), canRequestSave: () => isPresentationOwnerMutationAllowed(owner) });
    const units = options.units;
    const unitIds = new Set<string>();
    const unitDisposers: Array<() => void> = [];
    for (const unit of units) {
        if (!unit) {
            throw new Error('createSaveController units must not include null/undefined');
        }
        if (typeof unit.id !== 'string') {
            throw new Error('createSaveController units must provide a string id');
        }
        const normalizedId = unit.id.trim();
        if (!normalizedId) {
            throw new Error('createSaveController units must provide a non-empty id');
        }
        if (unitIds.has(normalizedId)) {
            throw new Error(`createSaveController units include duplicate id "${normalizedId}"`);
        }
        unitIds.add(normalizedId);
        unitDisposers.push(scope.registerUnit(unit));
    }

    let binding: SaveBinding | null = null;
    let bindingToken: symbol | null = null;
    let disposed = false;
    const headerContextId = options.headerContextId;
    const headerPriority = options.headerPriority;
    const requestContextLabel = options.requestContextLabel;
    let requestInFlight: Promise<void> | null = null;
    let admitting = false;
    let unregisterProtection: (() => void) | null = null;
    let protectionSubscription: (() => void) | null = null;
    const isRequestBusy = (): boolean => admitting || requestInFlight !== null || scope.isSaving();
    const isDestructionBlocked = (): boolean => isRequestBusy() || options.isDestructionBlocked?.() === true;
    const synchronizeProtection = (): void => {
        if (disposed || !isPresentationOwnerCurrent(owner)) {
            unregisterProtection?.();
            unregisterProtection = null;
            const release = protectionSubscription;
            protectionSubscription = null;
            release?.();
            return;
        }
        if (isPresentationOwnerActive(owner)) unregisterProtection ??= registerDirtyStateGuard(() => (isDestructionBlocked() ? navigationResult.block('save-in-progress') : true), { owner, hasUnsavedChanges: () => isDestructionBlocked() || scope.hasChanges(), getProtectionRevision: scope.getProtectionRevision, isDestructionBlocked, subscribeProtection: scope.subscribe });
    };
    const ensureProtectionRegistered = (): void => {
        if (owner.type !== 'global' && !protectionSubscription) {
            const release = owner.presentation.subscribe(synchronizeProtection);
            if (disposed || !isPresentationOwnerCurrent(owner)) release();
            else protectionSubscription = release;
        }
        synchronizeProtection();
    };
    const invokeCallback = (callback: () => void | Promise<void>): void | Promise<void> => {
        admitting = true;
        try {
            return callback();
        } finally {
            admitting = false;
        }
    };
    const ownsLifetime = (): boolean => !disposed && isPresentationOwnerCurrent(owner) && (options.isCurrent?.() ?? true);
    const executeSave = async (context: string): Promise<void> => {
        const outcome = await requestSaveSafely(scope, context);
        if (!ownsLifetime()) return;
        if (outcome === 'saved') {
            await invokeCallback(() => options.onSaveComplete?.());
        }
        if (!ownsLifetime()) return;
        if (outcome === 'saved' || outcome === 'degraded' || outcome === 'stopped') {
            await invokeCallback(() => options.onSaveSettled?.(outcome));
        }
    };
    const requestSaveWithContext = (context: string): Promise<void> => {
        if (disposed || admitting || scope.isInvokingCallback()) return Promise.resolve();
        if (requestInFlight !== null) {
            return requestInFlight;
        }
        admitting = true;
        let operation: Promise<void>;
        try {
            if (!ownsLifetime() || !isPresentationOwnerMutationAllowed(owner)) return Promise.resolve();
            ensureProtectionRegistered();
            const release = options.admission?.acquire() ?? null;
            if (options.admission && !release) return Promise.resolve();
            if (!ownsLifetime() || !isPresentationOwnerMutationAllowed(owner)) {
                release?.();
                return Promise.resolve();
            }
            operation = executeSave(context).finally(() => release?.());
        } finally {
            admitting = false;
        }
        const trackedOperation = operation.then(
            (): void => {
                if (requestInFlight === trackedOperation) {
                    requestInFlight = null;
                    scope.notifyChanged();
                }
            },
            (error): never => {
                if (requestInFlight === trackedOperation) {
                    requestInFlight = null;
                    scope.notifyChanged();
                }
                throw ensureError(error);
            }
        );
        requestInFlight = trackedOperation;
        return trackedOperation;
    };
    const requestSave = (): Promise<void> => requestSaveWithContext(requestContextLabel);

    return {
        owner,
        attach(attachOptions: SaveControllerAttachOptions): void {
            if (disposed) {
                throw new Error('Save controller has been disposed');
            }
            if (!attachOptions) {
                throw new Error('Save controller attach() requires options');
            }
            ensureProtectionRegistered();
            const token = Symbol('save-binding');
            bindingToken = token;
            const previous = binding;
            binding = null;
            try {
                previous?.dispose();
            } catch (error) {
                if (binding === null) binding = previous;
                throw ensureError(error);
            }
            if (disposed || bindingToken !== token) return;
            const incoming = bindSaveScope({
                scope,
                owner,
                requestSave: requestSaveWithContext,
                isRequestInFlight: () => requestInFlight !== null,
                canRequestSave: () => isPresentationOwnerMutationAllowed(owner) && (options.admission?.canAcquire() ?? true),
                headerContextId,
                headerPriority,
                resolveSaveButtons: attachOptions.resolveSaveButtons,
                enableHeaderAction: attachOptions.enableHeaderAction,
                onBusyChange: attachOptions.onBusyChange,
                busyRoots: attachOptions.busyRoots,
                autoNotifyRoot: attachOptions.autoNotifyRoot ?? null,
                autoNotifyAdditionalRoots: attachOptions.autoNotifyAdditionalRoots,
                additionalDirtyEventNames: attachOptions.additionalDirtyEventNames,
                buttonDisabledClassName: attachOptions.buttonDisabledClassName,
                buttonDirtyClassName: attachOptions.buttonDirtyClassName
            });
            if (disposed || bindingToken !== token) {
                incoming.dispose();
                return;
            }
            binding = incoming;
            try {
                incoming.sync();
            } catch (error) {
                if (binding === incoming) binding = null;
                try {
                    incoming.dispose();
                } catch (cleanupError) {
                    throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Save binding initialization and cleanup failed');
                }
                throw ensureError(error);
            }
        },
        hasChanges(): boolean {
            return scope.hasChanges();
        },
        canSave(): boolean {
            return isPresentationOwnerMutationAllowed(owner) && (options.admission?.canAcquire() ?? true) && scope.canSave();
        },
        isSaving(): boolean {
            return scope.isSaving();
        },
        notifyChanged(): void {
            scope.notifyChanged();
        },
        requestSave,
        dispose(): void {
            if (disposed) {
                return;
            }
            disposed = true;
            bindingToken = null;
            unregisterProtection?.();
            unregisterProtection = null;
            const releaseProtection = protectionSubscription;
            protectionSubscription = null;
            releaseProtection?.();
            binding?.dispose();
            binding = null;
            for (const disposeUnit of unitDisposers) {
                disposeUnit();
            }
            unitDisposers.length = 0;
            unitIds.clear();
            scope.dispose();
        }
    };
};

export { createSaveController };
export type { CreateSaveControllerOptions, SaveAdmission, SaveController, SaveControllerAttachOptions };
