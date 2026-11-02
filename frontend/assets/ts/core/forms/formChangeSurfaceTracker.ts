/* SoAI - Shared forms form change surface tracker [frontend/assets/ts/core/forms/formChangeSurfaceTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isNamedFormField, readFormControlValue, type NamedFormField } from '@core/dom/formFields.ts';
import { FIELD_CHANGE_SURFACE_CLASS } from '@core/forms/fieldSurface.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type FormChangeSurfaceTracker = {
    captureBaseline: () => void;
    sync: () => void;
    hasChanges: () => boolean;
    clear: () => void;
};

const CONTROL_SELECTOR = `.${FIELD_CHANGE_SURFACE_CLASS} input, .${FIELD_CHANGE_SURFACE_CLASS} select, .${FIELD_CHANGE_SURFACE_CLASS} textarea`;

const resolveControlKey = (control: NamedFormField): string => {
    const id = control.id.trim();
    if (id) {
        return id;
    }
    const name = control.name.trim();
    if (name) {
        return name;
    }
    throw new Error('Tracked form control must define an id or name');
};

const collectControls = (root: Element): Map<string, NamedFormField> => {
    const controls = new Map<string, NamedFormField>();
    for (const element of dom.resolveAll(CONTROL_SELECTOR, root)) {
        if (!isNamedFormField(element)) {
            continue;
        }
        controls.set(resolveControlKey(element), element);
    }
    return controls;
};

const createFormChangeSurfaceTracker = (root: Element): FormChangeSurfaceTracker => {
    let controls = collectControls(root);
    const baselineValues = new Map<string, JsonValue>();
    const tracker = new FieldStateTracker({
        getElement: (key: string): Element | null => controls.get(key) ?? null,
        getCurrentValue: (key: string): JsonValue | null => {
            const control = controls.get(key);
            return control ? readFormControlValue(control) : null;
        },
        getOriginalValue: (key: string): JsonValue | null => baselineValues.get(key) ?? null
    });

    const refreshControls = (): void => {
        controls = collectControls(root);
    };

    const captureBaseline = (): void => {
        refreshControls();
        baselineValues.clear();
        for (const [key, control] of controls) {
            baselineValues.set(key, readFormControlValue(control));
        }
        tracker.clearAll();
        for (const key of controls.keys()) {
            tracker.update(key);
        }
    };

    const sync = (): void => {
        refreshControls();
        for (const key of controls.keys()) {
            if (!baselineValues.has(key)) {
                const control = controls.get(key);
                baselineValues.set(key, control ? readFormControlValue(control) : null);
            }
            tracker.update(key);
        }
    };

    return {
        captureBaseline,
        sync,
        hasChanges: (): boolean => tracker.hasPendingChanges(),
        clear: (): void => {
            tracker.clearAll();
            baselineValues.clear();
        }
    };
};

export { createFormChangeSurfaceTracker };
export type { FormChangeSurfaceTracker };
