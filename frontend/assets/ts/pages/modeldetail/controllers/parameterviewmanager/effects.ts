/* SoAI - Model detail page control layer parameter view manager effects [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import { isParameterUsingDefault, normalizeParameterValue } from '@pages/modeldetail/controllers/parameterviewmanager/state.ts';
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
    setParameterDefaultState: (parameterKey: string, isDefault: boolean) => void;
    setParameterModifiedState: (parameterKey: string, isModified: boolean) => void;
    handleModificationStateChange: () => void;
}

const setParameterDefaultState = (host: ParameterViewHost, resolveElement: ResolveElement, parameterKey: string, isDefault: boolean): void => {
    const element = resolveElement(parameterKey);
    if (element) {
        host.pageDom.toggleClass(element, 'default-param', Boolean(isDefault));
    }
};

const applyDefaultHighlights = (dependencies: ParameterEffectDependencies): void => {
    dependencies.state.getParameterKeys().forEach((parameterKey) => {
        const isDefault = isParameterUsingDefault(dependencies.state, parameterKey);
        setParameterDefaultState(dependencies.host, dependencies.resolveElement, parameterKey, isDefault);
    });
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
    const isDefault = isParameterUsingDefault(dependencies.state, parameterKey);
    setParameterDefaultState(dependencies.host, dependencies.resolveElement, parameterKey, isDefault);
    dependencies.setParameterModifiedState(parameterKey, result.isModified);
    dependencies.handleModificationStateChange();
};

const refreshModificationState = (state: ParameterStateManager, setModifiedState: (parameterKey: string, isModified: boolean) => void, handleModificationStateChange: () => void): void => {
    state.getParameterKeys().forEach((parameterKey) => {
        setModifiedState(parameterKey, state.isParameterModified(parameterKey));
    });
    handleModificationStateChange();
};

const resetParameterValue = ({ state, parameterKey, updateParameterUI, setParameterDefaultState: setDefaultState, setParameterModifiedState: setModifiedState, handleModificationStateChange }: ParameterResetDependencies): void => {
    const original = state.getOriginalParameter(parameterKey);
    if (!original) {
        return;
    }
    const restored = state.resetParameter(parameterKey);
    const fallback = original.definition?.default ?? null;
    const displayValue = sanitizeParameterValue(original, restored ?? fallback, { treatDefaultAsNull: false });
    updateParameterUI(parameterKey, displayValue);
    setDefaultState(parameterKey, isParameterUsingDefault(state, parameterKey));
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
            setDefaultState(linkedParameterKey, isParameterUsingDefault(state, linkedParameterKey));
            setModifiedState(linkedParameterKey, state.isParameterModified(linkedParameterKey));
        }
    }
    handleModificationStateChange();
};

export { applyDefaultHighlights, createParameterFieldStateTracker, refreshModificationState, resetParameterValue, setParameterDefaultState, updateParameterValue };
