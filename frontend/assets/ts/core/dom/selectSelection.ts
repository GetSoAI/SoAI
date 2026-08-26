/* SoAI - Shared DOM select selection [frontend/assets/ts/core/dom/selectSelection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const syncSelectDefaultSelectedToCurrent = (select: HTMLSelectElement): void => {
    const options = Array.from(select.options);
    if (options.length === 0) {
        return;
    }

    for (const option of options) {
        const selected = option.selected;
        option.defaultSelected = selected;
        if (selected) {
            option.setAttribute('selected', '');
        } else {
            option.removeAttribute('selected');
        }
    }
};

const getSelectDefaultValue = (select: HTMLSelectElement): string => {
    const options = Array.from(select.options);
    const defaultOption = options.find((option) => option.defaultSelected);
    if (defaultOption) {
        return defaultOption.value;
    }
    const selectedOption = select.options.item(select.selectedIndex);
    return selectedOption ? selectedOption.value : '';
};

const setSelectValueAndSyncDefault = (select: HTMLSelectElement, value: string): void => {
    select.value = value;
    syncSelectDefaultSelectedToCurrent(select);
};

const setSelectSelectedIndexAndSyncDefault = (select: HTMLSelectElement, selectedIndex: number): void => {
    select.selectedIndex = selectedIndex;
    syncSelectDefaultSelectedToCurrent(select);
};

export { getSelectDefaultValue, setSelectSelectedIndexAndSyncDefault, setSelectValueAndSyncDefault, syncSelectDefaultSelectedToCurrent };
