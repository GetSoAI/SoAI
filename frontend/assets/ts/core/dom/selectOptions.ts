/* SoAI - Shared DOM select options [frontend/assets/ts/core/dom/selectOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';

interface SelectOptionDefinition {
    value: string;
    label: string;
    disabled?: boolean;
    selected?: boolean;
}

interface SelectOptionGroupDefinition {
    label: string;
    options: ReadonlyArray<SelectOptionDefinition>;
    disabled?: boolean;
}

type SelectEntryDefinition = SelectOptionDefinition | SelectOptionGroupDefinition;

const isSelectOptionGroupDefinition = (entry: SelectEntryDefinition): entry is SelectOptionGroupDefinition => {
    return 'options' in entry && isArray(entry.options);
};

const createOptionElement = (documentRef: Document, definition: SelectOptionDefinition): HTMLOptionElement => {
    const option = documentRef.createElement('option');
    option.value = definition.value;
    option.textContent = definition.label;
    option.disabled = definition.disabled === true;
    const selected = definition.selected === true;
    option.selected = selected;
    option.defaultSelected = selected;
    if (selected) {
        option.setAttribute('selected', '');
    }
    return option;
};

const createGroupElement = (documentRef: Document, definition: SelectOptionGroupDefinition): HTMLOptGroupElement => {
    const group = documentRef.createElement('optgroup');
    group.label = definition.label;
    group.disabled = definition.disabled === true;
    for (const optionDefinition of definition.options) {
        group.appendChild(createOptionElement(documentRef, optionDefinition));
    }
    return group;
};

const replaceSelectOptions = (select: HTMLSelectElement, entries: ReadonlyArray<SelectEntryDefinition>): void => {
    const documentRef = select.ownerDocument;
    const fragment = documentRef.createDocumentFragment();
    for (const entry of entries) {
        if (isSelectOptionGroupDefinition(entry)) {
            fragment.appendChild(createGroupElement(documentRef, entry));
            continue;
        }
        fragment.appendChild(createOptionElement(documentRef, entry));
    }
    select.replaceChildren(fragment);
};

export { replaceSelectOptions };
export type { SelectEntryDefinition, SelectOptionDefinition, SelectOptionGroupDefinition };
