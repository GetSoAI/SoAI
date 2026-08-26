/* SoAI - Shared named form field lookup and signature helpers [frontend/assets/ts/core/dom/formFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';

type NamedFormField = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

interface NamedFormFieldHost {
    root: Element;
    context: string;
}

interface FormSignatureField {
    name: string;
    value: string;
}

const isNamedFormField = (value: Element): value is NamedFormField => {
    return value instanceof HTMLInputElement || value instanceof HTMLSelectElement || value instanceof HTMLTextAreaElement;
};

const requireSafeFormFieldName = (name: string, context: string): string => {
    if (!/^[a-z0-9_-]+$/i.test(name)) {
        throw new Error(`${context} form field selector is invalid: ${name}`);
    }
    return name;
};

const namedFormFieldSelector = (name: string, context: string): string => {
    return `[name="${requireSafeFormFieldName(name, context)}"]`;
};

const isVisibleNamedFormField = (field: NamedFormField): boolean => {
    return !field.hidden && field.closest('[hidden]') === null;
};

const resolveNamedFormFields = (host: NamedFormFieldHost, name: string): NamedFormField[] => {
    const fields: NamedFormField[] = [];
    dom.resolveAll(namedFormFieldSelector(name, host.context), host.root).forEach((element) => {
        if (isNamedFormField(element)) {
            fields.push(element);
        }
    });
    return fields;
};

const requireNamedFormField = (host: NamedFormFieldHost, name: string): NamedFormField => {
    const fields = resolveNamedFormFields(host, name);
    const visibleField = fields.find((field) => isVisibleNamedFormField(field));
    if (visibleField !== undefined) {
        return visibleField;
    }
    const firstField = fields[0];
    if (firstField !== undefined) {
        return firstField;
    }
    throw new Error(`${host.context} form field is invalid: ${name}`);
};

const readNamedFormFieldTrimmedValue = (host: NamedFormFieldHost, name: string): string => {
    const field = requireNamedFormField(host, name);
    return field instanceof HTMLSelectElement ? readTrimmedSelectValue(field) : readTrimmedInputValue(field);
};

const setNamedFormFieldValue = (host: NamedFormFieldHost, name: string, value: string): void => {
    requireNamedFormField(host, name).value = value;
};

const setNamedFormFieldValues = (host: NamedFormFieldHost, name: string, value: string): void => {
    const fields = resolveNamedFormFields(host, name);
    if (fields.length === 0) {
        throw new Error(`${host.context} form field is invalid: ${name}`);
    }
    fields.forEach((field) => {
        field.value = value;
    });
};

const buildFormSignature = (fields: readonly FormSignatureField[]): string => {
    return JSON.stringify(fields);
};

const buildNamedFormFieldSignature = (host: NamedFormFieldHost, names: readonly string[]): string => {
    return buildFormSignature(names.map((name) => ({ name, value: readNamedFormFieldTrimmedValue(host, name) })));
};

export { buildFormSignature, buildNamedFormFieldSignature, isNamedFormField, readNamedFormFieldTrimmedValue, requireNamedFormField, resolveNamedFormFields, setNamedFormFieldValue, setNamedFormFieldValues };
export type { FormSignatureField, NamedFormField, NamedFormFieldHost };
