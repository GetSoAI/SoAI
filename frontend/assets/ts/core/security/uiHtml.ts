/* SoAI - Shared security UI HTML [frontend/assets/ts/core/security/uiHtml.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { escapeAttribute, escapeHtml } from '@core/security/textSanitizer.ts';
import { createTrustedHtmlValue, isTrustedHtml, type TrustedHtml } from '@core/security/htmlSanitizer.ts';

const staticUiHtml = (strings: TemplateStringsArray): TrustedHtml => {
    if (strings.length !== 1 || strings.raw.length !== 1) {
        throw new Error('staticUiHtml accepts static template markup without interpolations');
    }
    return createTrustedHtmlValue(strings[0] ?? '');
};

const EMPTY_UI_HTML: TrustedHtml = createTrustedHtmlValue('');
type UiHtmlValue = TrustedHtml | string | number | boolean | bigint | symbol | null | undefined | void;
type UiAttributeValue = string | number | boolean | null | undefined;

const validateUiAttributeName = (name: string): void => {
    if (!/^[a-zA-Z][a-zA-Z0-9_:-]*$/.test(name)) {
        throw new Error(`Invalid UI attribute name: ${name}`);
    }
    const normalizedName = name.toLowerCase();
    if (normalizedName.startsWith('on') || ['action', 'formaction', 'href', 'poster', 'src', 'srcdoc', 'style', 'xlink:href'].includes(normalizedName)) {
        throw new Error(`Unsafe UI attribute name: ${name}`);
    }
};

const uiAttr = <T>(value: T): TrustedHtml => {
    return createTrustedHtmlValue(escapeAttribute(value));
};

const uiText = <T>(value: T): TrustedHtml => {
    return createTrustedHtmlValue(escapeHtml(value));
};

const joinUiHtml = (values: readonly TrustedHtml[]): TrustedHtml => {
    const parts: string[] = [];
    for (const value of values) {
        if (!isTrustedHtml(value)) {
            throw new Error('joinUiHtml requires TrustedHtml values');
        }
        parts.push(value.html);
    }
    return createTrustedHtmlValue(parts.join(''));
};

const uiAttributes = (attributes: Readonly<Record<string, UiAttributeValue>>): TrustedHtml => {
    const parts: string[] = [];
    for (const [name, value] of Object.entries(attributes)) {
        validateUiAttributeName(name);
        if (value === null || value === undefined || value === false) {
            continue;
        }
        if (value === true) {
            parts.push(` ${name}`);
            continue;
        }
        parts.push(` ${name}="${escapeAttribute(value)}"`);
    }
    return createTrustedHtmlValue(parts.join(''));
};

const uiHtml = (strings: TemplateStringsArray, ...values: UiHtmlValue[]): TrustedHtml => {
    const parts: string[] = [];
    for (let index = 0; index < strings.length; index += 1) {
        const raw = strings[index];
        if (raw) {
            parts.push(String(raw));
        }
        if (index >= values.length) {
            continue;
        }
        const value = values[index];
        if (isTrustedHtml(value)) {
            parts.push(value.html);
        } else {
            parts.push(escapeHtml(value));
        }
    }
    return createTrustedHtmlValue(parts.join(''));
};

export { EMPTY_UI_HTML, joinUiHtml, staticUiHtml, uiAttr, uiAttributes, uiHtml, uiText };
export type { UiAttributeValue };
