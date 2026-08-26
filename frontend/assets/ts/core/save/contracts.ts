/* SoAI - SaveScope contract types [frontend/assets/ts/core/save/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface SaveUnitStopResult {
    type: 'stop';
}

interface SaveUnitContinueDegradedResult {
    type: 'continue-degraded';
}

type SaveUnitResult = void | SaveUnitStopResult | SaveUnitContinueDegradedResult;

interface PreparedSaveUnit {
    isValid?: () => boolean;
    save: () => SaveUnitResult | Promise<SaveUnitResult>;
}

interface SaveUnit {
    id: string;
    hasChanges: () => boolean;
    save: () => SaveUnitResult | Promise<SaveUnitResult>;
    isValid?: () => boolean;
    prepare?: () => PreparedSaveUnit;
}

type SaveRequestOutcome = 'saved' | 'degraded' | 'stopped' | 'noChanges' | 'invalid' | 'busy' | 'blocked' | 'disposed' | 'debounced';

interface SaveScope {
    registerUnit: (unit: SaveUnit) => () => void;
    hasChanges: () => boolean;
    canSave: () => boolean;
    requestSave: () => Promise<SaveRequestOutcome>;
    isSaving: () => boolean;
    notifyChanged: () => void;
    subscribe: (listener: () => void) => () => void;
    dispose: () => void;
}

interface SaveBinding {
    sync: () => void;
    dispose: () => void;
}

interface BindSaveScopeOptions {
    scope: SaveScope;
    requestSave: (context: string) => Promise<void>;
    canRequestSave?: (() => boolean) | undefined;
    headerContextId: string;
    headerPriority?: number | undefined;
    resolveSaveButtons: () => readonly HTMLButtonElement[];
    enableHeaderAction?: boolean | undefined;
    onBusyChange?: ((busy: boolean) => void) | undefined;
    busyRoots?: readonly Element[] | undefined;
    autoNotifyRoot?: Element | null;
    autoNotifyAdditionalRoots?: readonly Element[] | undefined;
    additionalDirtyEventNames?: readonly string[] | undefined;
    buttonDisabledClassName?: string | null | undefined;
    buttonDirtyClassName?: string | null | undefined;
}

export type { BindSaveScopeOptions, PreparedSaveUnit, SaveBinding, SaveRequestOutcome, SaveScope, SaveUnit, SaveUnitContinueDegradedResult, SaveUnitResult, SaveUnitStopResult };
