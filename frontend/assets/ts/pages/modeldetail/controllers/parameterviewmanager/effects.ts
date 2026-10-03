/* SoAI - Model detail page control layer parameter view manager effects [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import { PARAMETER_CUSTOM_BADGE_SELECTOR } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { normalizeParameterValue } from '@pages/modeldetail/controllers/parameterviewmanager/state.ts';
import type { ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { areValuesEqual, sanitizeParameterValue } from '@pages/modeldetail/mappers/parameterValueNormalization.ts';

type ResolveElement = (parameterKey: string) => Element | null;

interface ParameterEffectDependencies {
    host: ParameterViewHost;
    state: ParameterStateManager;
    resolveElement: ResolveElement;
}

interface ParameterUpdateDependencies extends ParameterEffectDependencies {
    setParameterModifiedState: (parameterKey: string, isModified: boolean) => void;
    handleModificationStateChange: () => void;
}

interface ParameterResetDependencies {
    state: ParameterStateManager;
    parameterKey: string;
    updateParameterUI: (parameterKey: string, value: ParameterValue) => void;
    syncParameterCustomizedState: (parameterKey: string) => void;
    setParameterModifiedState: (parameterKey: string, isModified: boolean) => void;
    handleModificationStateChange: () => void;
}

const syncParameterCustomizedState = (dependencies: ParameterEffectDependencies, parameterKey: string): void => {
    const item = dependencies.resolveElement(parameterKey);
    const badge = item ? dependencies.host.pageDom.optional(PARAMETER_CUSTOM_BADGE_SELECTOR, item) : null;
    if (badge) {
        dependencies.host.pageDom.toggleClass(badge, CSS_CLASSES.HIDDEN, !dependencies.state.isParameterCustomized(parameterKey));
    }
};

const createParameterFieldStateTracker = (state: ParameterStateManager, resolveElement: ResolveElement): FieldStateTracker =>
    new FieldStateTracker({
        getElement: (key: string) => resolveElement(key),
        getCurrentValue: (key: string) => {
            const parameter = state.getParameter(key);
            return parameter ? sanitizeParameterValue(parameter, parameter.currentValue) : undefined;
        },
        getOriginalValue: (key: string) => {
            const parameter = state.getOriginalParameter(key);
            return parameter ? sanitizeParameterValue(parameter, parameter.currentValue) : undefined;
        },
        comparator: (current, original) => areValuesEqual(current, original)
    });

const updateParameterValue = (dependencies: ParameterUpdateDependencies, parameterKey: string, value: ParameterValue): void => {
    const parameter = dependencies.state.getParameter(parameterKey);
    if (!parameter) {
        return;
    }
    const normalized = normalizeParameterValue(dependencies.state, parameterKey, value);
    const result = dependencies.state.setParameterValue(parameterKey, normalized);
    if (!result) {
        return;
    }
    syncParameterCustomizedState(dependencies, parameterKey);
    dependencies.setParameterModifiedState(parameterKey, result.isModified);
    dependencies.handleModificationStateChange();
};

const refreshModificationState = (state: ParameterStateManager, setModifiedState: (parameterKey: string, isModified: boolean) => void, handleModificationStateChange: () => void): void => {
    state.getParameterKeys().forEach((parameterKey) => {
        setModifiedState(parameterKey, state.isParameterModified(parameterKey));
    });
    handleModificationStateChange();
};

const resetParameterValue = ({ state, parameterKey, updateParameterUI, syncParameterCustomizedState: syncCustomizedState, setParameterModifiedState: setModifiedState, handleModificationStateChange }: ParameterResetDependencies): void => {
    const original = state.getOriginalParameter(parameterKey);
    if (!original) {
        return;
    }
    const restored = state.resetParameter(parameterKey);
    const fallback = original.definition?.default ?? null;
    const displayValue = sanitizeParameterValue(original, restored ?? fallback, { treatDefaultAsNull: false });
    updateParameterUI(parameterKey, displayValue);
    syncCustomizedState(parameterKey);
    setModifiedState(parameterKey, state.isParameterModified(parameterKey));
    const linkedParameterKey = state.getLinkedParameterKey(parameterKey);
    if (linkedParameterKey) {
        const linked = state.getParameter(linkedParameterKey);
        if (linked) {
            const linkedFallback = linked.definition?.default ?? null;
            const linkedDisplayValue = sanitizeParameterValue(linked, linked.currentValue ?? linkedFallback, {
                treatDefaultAsNull: false
            });
            updateParameterUI(linkedParameterKey, linkedDisplayValue);
            syncCustomizedState(linkedParameterKey);
            setModifiedState(linkedParameterKey, state.isParameterModified(linkedParameterKey));
        }
    }
    handleModificationStateChange();
};

export { createParameterFieldStateTracker, refreshModificationState, resetParameterValue, syncParameterCustomizedState, updateParameterValue };
