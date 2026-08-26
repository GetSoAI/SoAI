/* SoAI - Save controller (canonical page surface) [frontend/assets/ts/core/save/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
    headerContextId: string;
    headerPriority?: number | undefined;
    requestContextLabel: string;
    units: readonly SaveUnit[];
    onSaveComplete?: (() => void | Promise<void>) | undefined;
    onSaveSettled?: ((outcome: 'saved' | 'degraded' | 'stopped') => void | Promise<void>) | undefined;
    admission?: SaveAdmission | undefined;
};

type SaveAdmission = {
    canAcquire: () => boolean;
    acquire: () => (() => void) | null;
};

type SaveController = {
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
    const scope = createSaveScope();
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
    let disposed = false;
    const headerContextId = options.headerContextId;
    const headerPriority = options.headerPriority;
    const requestContextLabel = options.requestContextLabel;
    let requestInFlight: Promise<void> | null = null;
    const executeSave = async (context: string): Promise<void> => {
        const outcome = await requestSaveSafely(scope, context);
        if (outcome === 'saved') {
            await options.onSaveComplete?.();
        }
        if (outcome === 'saved' || outcome === 'degraded' || outcome === 'stopped') {
            await options.onSaveSettled?.(outcome);
        }
    };
    const requestSaveWithContext = (context: string): Promise<void> => {
        if (requestInFlight !== null) {
            return requestInFlight;
        }
        const release = options.admission?.acquire() ?? null;
        if (options.admission && !release) {
            return Promise.resolve();
        }
        const operation = executeSave(context).finally(() => release?.());
        const trackedOperation = operation.then(
            (): void => {
                if (requestInFlight === trackedOperation) requestInFlight = null;
            },
            (error): never => {
                if (requestInFlight === trackedOperation) requestInFlight = null;
                throw error;
            }
        );
        requestInFlight = trackedOperation;
        return trackedOperation;
    };
    const requestSave = (): Promise<void> => requestSaveWithContext(requestContextLabel);

    return {
        attach(attachOptions: SaveControllerAttachOptions): void {
            if (disposed) {
                throw new Error('Save controller has been disposed');
            }
            if (!attachOptions) {
                throw new Error('Save controller attach() requires options');
            }
            binding?.dispose();
            binding = bindSaveScope({
                scope,
                requestSave: requestSaveWithContext,
                canRequestSave: () => options.admission?.canAcquire() ?? true,
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
        },
        hasChanges(): boolean {
            return scope.hasChanges();
        },
        canSave(): boolean {
            return (options.admission?.canAcquire() ?? true) && scope.canSave();
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
