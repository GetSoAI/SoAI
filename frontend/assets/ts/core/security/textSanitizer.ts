/* SoAI - Shared security text sanitizer [frontend/assets/ts/core/security/textSanitizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const stripControlCharacters = (input: string): string => {
    if (!input) {
        return '';
    }
    const characters: string[] = [];
    for (let index = 0; index < input.length; index += 1) {
        const code = input.charCodeAt(index);
        const isDisallowedControl = (code >= 0 && code <= 8) || code === 11 || code === 12 || (code >= 14 && code <= 31) || code === 127;
        if (isDisallowedControl) {
            continue;
        }
        characters.push(input.charAt(index));
    }
    return characters.join('');
};

interface SanitizeTextOptions {
    trim?: boolean;
}

const sanitizeText = <T>(value?: T, options: SanitizeTextOptions = {}): string => {
    const { trim = true } = options;
    const stringValue = String(value ?? '');
    const normalized = trim ? stringValue.trim() : stringValue;
    return stripControlCharacters(normalized);
};

const escapeHtml = <T>(value?: T): string => sanitizeText(value, { trim: false }).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');

const escapeAttribute = <T>(value?: T): string =>
    escapeHtml(value)
        .replace(/`/g, '&#096;')
        .replace(/[\n\r\t]/g, ' ');

export { stripControlCharacters, sanitizeText, escapeHtml, escapeAttribute };
export type { SanitizeTextOptions };
