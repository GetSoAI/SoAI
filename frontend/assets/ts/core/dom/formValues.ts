/* SoAI - Shared DOM form values [frontend/assets/ts/core/dom/formValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const readTrimmedInputValue = (input: HTMLInputElement | HTMLTextAreaElement): string => input.value.trim();

const readTrimmedSelectValue = (select: HTMLSelectElement): string => select.value.trim();

type SelectedOptionDataKey = 'filesystem' | 'fingerprint' | 'parentFingerprint';

const readSelectedOptionTrimmedDataValue = (select: HTMLSelectElement, key: SelectedOptionDataKey): string | null => {
    const selectedOption = select.selectedOptions[0];
    if (!selectedOption) {
        return null;
    }
    let value: string | undefined;
    if (key === 'filesystem') {
        value = selectedOption.dataset['filesystem'];
    } else if (key === 'fingerprint') {
        value = selectedOption.dataset['fingerprint'];
    } else {
        value = selectedOption.dataset['parentFingerprint'];
    }
    if (typeof value !== 'string') {
        return null;
    }
    const normalized = value.trim();
    return normalized || null;
};

const readOptionalTrimmedInputValue = (input: HTMLInputElement | HTMLTextAreaElement | null): string | null => {
    if (input === null) {
        return null;
    }
    const value = readTrimmedInputValue(input);
    return value ? value : null;
};

const requireInputNumberBounds = (minimum: number, maximum: number): void => {
    if (maximum < minimum) {
        throw new Error('Input integer bounds are invalid');
    }
};

const readFiniteInputValueOrNull = (input: HTMLInputElement): number | null => {
    const value = readTrimmedInputValue(input);
    if (!value) {
        return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const readBoundedFlooredIntegerInputValueOrNull = (input: HTMLInputElement, minimum: number, maximum: number): number | null => {
    requireInputNumberBounds(minimum, maximum);
    const parsed = readFiniteInputValueOrNull(input);
    if (parsed === null || parsed < minimum || parsed > maximum) {
        return null;
    }
    return Math.floor(parsed);
};

const readBoundedCeiledIntegerInputValueOrNull = (input: HTMLInputElement, minimum: number, maximum: number): number | null => {
    requireInputNumberBounds(minimum, maximum);
    const parsed = readFiniteInputValueOrNull(input);
    if (parsed === null || parsed < minimum || parsed > maximum) {
        return null;
    }
    return Math.ceil(parsed);
};

export { readBoundedCeiledIntegerInputValueOrNull, readBoundedFlooredIntegerInputValueOrNull, readFiniteInputValueOrNull, readOptionalTrimmedInputValue, readSelectedOptionTrimmedDataValue, readTrimmedInputValue, readTrimmedSelectValue };
