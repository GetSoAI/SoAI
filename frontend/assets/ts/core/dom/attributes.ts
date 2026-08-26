/* SoAI - Shared DOM attributes [frontend/assets/ts/core/dom/attributes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const optionalTrimmedAttributeValue = (rawValue: string | null): string | null => {
    const trimmed = toTrimmedString(rawValue);
    return trimmed ? trimmed : null;
};

const optionalTrimmedStringAttribute = (element: Element, attributeName: string): string | null => {
    return optionalTrimmedAttributeValue(element.getAttribute(attributeName));
};

const normalizeDataAttributeName = (key: string): string => {
    const normalized = key
        .trim()
        .replace(/^data[-_]?/i, '')
        .replace(/_/g, '-')
        .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
        .toLowerCase();
    if (!normalized) {
        throw new Error('Data attribute key is required');
    }
    return `data-${normalized}`;
};

const optionalTrimmedDataAttribute = (element: Element, key: string): string | null => {
    return optionalTrimmedStringAttribute(element, normalizeDataAttributeName(key));
};

const requireTrimmedDataAttribute = (element: Element, key: string, context: string): string => {
    const attributeName = normalizeDataAttributeName(key);
    const value = optionalTrimmedStringAttribute(element, attributeName);
    if (value === null) {
        throw new Error(`${context} requires ${attributeName}`);
    }
    return value;
};

const parseNonNegativeIntegerFromStringOrNull = (rawValue: string): number | null => {
    if (!/^[0-9]+$/.test(rawValue)) {
        return null;
    }
    const parsed = Number.parseInt(rawValue, 10);
    if (!Number.isInteger(parsed) || parsed < 0 || parsed > Number.MAX_SAFE_INTEGER) {
        return null;
    }
    return parsed;
};

const parseNonNegativeIntegerFromString = (rawValue: string, context: string): number => {
    const parsed = parseNonNegativeIntegerFromStringOrNull(rawValue);
    if (parsed === null) {
        throw new Error(`${context} must be a non-negative integer`);
    }
    return parsed;
};

const optionalNonNegativeIntegerAttribute = (element: Element, attributeName: string, context: string): number | null => {
    const value = optionalTrimmedStringAttribute(element, attributeName);
    if (value === null) {
        return null;
    }
    return parseNonNegativeIntegerFromString(value, `${context} ${attributeName}`);
};

const requireNonNegativeIntegerAttribute = (element: Element, attributeName: string, context: string): number => {
    const value = optionalNonNegativeIntegerAttribute(element, attributeName, context);
    if (value === null) {
        throw new Error(`${context} requires ${attributeName}`);
    }
    return value;
};

const optionalNonNegativeIntegerDataAttribute = (element: Element, key: string, context: string): number | null => {
    const value = optionalTrimmedDataAttribute(element, key);
    if (value === null) {
        return null;
    }
    return parseNonNegativeIntegerFromString(value, `${context} ${normalizeDataAttributeName(key)}`);
};

const requireNonNegativeIntegerDataAttribute = (element: Element, key: string, context: string): number => {
    const value = optionalNonNegativeIntegerDataAttribute(element, key, context);
    if (value === null) {
        throw new Error(`${context} requires ${normalizeDataAttributeName(key)}`);
    }
    return value;
};

const optionalBooleanFlagFromString = (rawValue: string): boolean => {
    const normalized = rawValue.trim().toLowerCase();
    if (!normalized) {
        return true;
    }
    if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') {
        return true;
    }
    if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') {
        return false;
    }
    throw new Error('Boolean flag must be a supported truthy/falsey token');
};

const parsePositiveCssPixelValue = (value: string | null, fallbackPx: number): number => {
    const normalized = optionalTrimmedAttributeValue(value);
    if (normalized === null) {
        return fallbackPx;
    }
    const numericText = normalized.endsWith('px') ? normalized.slice(0, -2).trim() : normalized;
    const parsed = Number(numericText);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackPx;
};

const parseFirstPositiveCssPixelValue = (value: string | null, fallbackPx: number): number => {
    const normalized = optionalTrimmedAttributeValue(value);
    if (normalized === null) {
        return fallbackPx;
    }
    const first = normalized.split(/\s+/)[0] ?? '';
    const numericText = first.endsWith('px') ? first.slice(0, -2).trim() : first;
    const parsed = Number(numericText);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackPx;
};

const optionalClosestElement = (element: Element, selector: string, root?: Element): Element | null => {
    const candidate = element.closest(selector);
    if (!candidate) {
        return null;
    }
    if (root && !root.contains(candidate)) {
        return null;
    }
    return candidate;
};

const requireClosestElement = (element: Element, selector: string, context: string, root?: Element): Element => {
    const candidate = optionalClosestElement(element, selector, root);
    if (!candidate) {
        throw new Error(`${context} requires ancestor ${selector}`);
    }
    return candidate;
};

export { normalizeDataAttributeName, optionalBooleanFlagFromString, optionalClosestElement, optionalNonNegativeIntegerAttribute, optionalNonNegativeIntegerDataAttribute, optionalTrimmedAttributeValue, optionalTrimmedDataAttribute, optionalTrimmedStringAttribute, parseFirstPositiveCssPixelValue, parseNonNegativeIntegerFromString, parseNonNegativeIntegerFromStringOrNull, parsePositiveCssPixelValue, requireClosestElement, requireNonNegativeIntegerAttribute, requireNonNegativeIntegerDataAttribute, requireTrimmedDataAttribute };
