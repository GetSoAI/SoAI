/* SoAI - Shared UI class names [frontend/assets/ts/core/ui/classNames.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export interface BaseClassNames {
    active?: string;
    hidden?: string;
    disabled?: string;
}

export interface RequiredClassNames {
    active: string;
    hidden: string;
    disabled: string;
}

export function validateClassNames(classNames: BaseClassNames | null | undefined, requiredKeys: readonly ['disabled'], context: string): Pick<RequiredClassNames, 'disabled'>;
export function validateClassNames(classNames: BaseClassNames | null | undefined, requiredKeys: readonly ['hidden', 'disabled'], context: string): Pick<RequiredClassNames, 'hidden' | 'disabled'>;
export function validateClassNames(classNames: BaseClassNames | null | undefined, requiredKeys: readonly ['active', 'hidden', 'disabled'], context: string): RequiredClassNames;
export function validateClassNames(classNames: BaseClassNames | null | undefined, requiredKeys: ReadonlyArray<keyof BaseClassNames>, context: string): BaseClassNames {
    if (!classNames) {
        throw new Error(`${context} requires class names configuration`);
    }
    for (const key of requiredKeys) {
        if (!classNames[key]) {
            throw new Error(`${context} requires ${key} class name`);
        }
    }

    if (requiredKeys.length === 1 && requiredKeys[0] === 'disabled') {
        const disabled = classNames.disabled;
        if (!disabled) {
            throw new Error(`${context} requires disabled class name`);
        }
        return { disabled };
    }

    if (requiredKeys.length === 2 && requiredKeys[0] === 'hidden' && requiredKeys[1] === 'disabled') {
        const hidden = classNames.hidden;
        const disabled = classNames.disabled;
        if (!hidden) {
            throw new Error(`${context} requires hidden class name`);
        }
        if (!disabled) {
            throw new Error(`${context} requires disabled class name`);
        }
        return { hidden, disabled };
    }

    if (requiredKeys.length === 3 && requiredKeys[0] === 'active' && requiredKeys[1] === 'hidden' && requiredKeys[2] === 'disabled') {
        const active = classNames.active;
        const hidden = classNames.hidden;
        const disabled = classNames.disabled;
        if (!active) {
            throw new Error(`${context} requires active class name`);
        }
        if (!hidden) {
            throw new Error(`${context} requires hidden class name`);
        }
        if (!disabled) {
            throw new Error(`${context} requires disabled class name`);
        }
        return { active, hidden, disabled };
    }

    return classNames;
}
