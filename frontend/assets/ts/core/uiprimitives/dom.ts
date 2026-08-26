/* SoAI - Shared UI primitives DOM contracts [frontend/assets/ts/core/uiprimitives/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { AttributeProps, ClassValue } from '@core/uiprimitives/types.ts';

const combineValues = (parts: string[], value: ClassValue): void => {
    if (!value) return;
    if (isString(value)) {
        value
            .split(/\s+/)
            .map((entry) => entry.trim())
            .filter(Boolean)
            .forEach((entry) => parts.push(entry));
        return;
    }
    if (Array.isArray(value)) {
        for (const entry of value) {
            combineValues(parts, entry);
        }
    }
};

const combineClasses = (...values: ClassValue[]): string => {
    const parts: string[] = [];
    for (const value of values) {
        combineValues(parts, value);
    }
    return parts.join(' ');
};

const cloneAttributes = (attributes: AttributeProps | undefined): Record<string, string | boolean | number | undefined> => (attributes ? { ...attributes } : {});

const renderAttributeMap = (values: Record<string, string | boolean | number | undefined> | undefined, prefix: string, boolValueless: boolean, escapeFunctionValue: (value: string) => string): string => {
    if (!values) return '';
    let output = '';
    for (const [key, value] of Object.entries(values)) {
        if (value !== false && value !== undefined) {
            const attribute = escapeFunctionValue(prefix + key);
            output += boolValueless && value === true ? ` ${attribute}` : ` ${attribute}="${escapeFunctionValue(String(value))}"`;
        }
    }
    return output;
};

const renderAria = (aria: AttributeProps | undefined, escapeFunctionValue: (value: string) => string): string => renderAttributeMap(aria, 'aria-', false, escapeFunctionValue);

const renderDataset = (dataset: AttributeProps | undefined, escapeFunctionValue: (value: string) => string): string => renderAttributeMap(dataset, 'data-', true, escapeFunctionValue);

const renderAttributes = (attributes: AttributeProps | undefined, escapeFunctionValue: (value: string) => string): string => renderAttributeMap(attributes, '', true, escapeFunctionValue);

export { cloneAttributes, combineClasses, renderAria, renderDataset, renderAttributes };
