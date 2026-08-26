/* SoAI - Shared primitives ID generator [frontend/assets/ts/core/primitives/idGenerator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';

const HEX_TABLE: readonly string[] = (() => {
    const table: string[] = new Array(256);
    for (let index = 0; index < 256; index += 1) {
        table[index] = (index + 0x100).toString(16).slice(1);
    }
    return Object.freeze(table);
})();

const ensureCrypto = (): Crypto => {
    const scope = getGlobalScope();
    const cryptoApi = scope.crypto;
    if (!cryptoApi || !isFunction(cryptoApi.getRandomValues)) {
        throw new Error('window.crypto.getRandomValues must be available for secure ID generation');
    }
    return cryptoApi;
};

const requireByte = (bytes: Uint8Array, index: number, description: string): number => {
    const value = bytes[index];
    if (value === undefined) {
        throw new Error(`${description} byte ${index} is missing`);
    }
    return value;
};

const requireHexPart = (hex: readonly string[], index: number): string => {
    const value = hex[index];
    if (value === undefined) {
        throw new Error(`HEX table entry ${index} is missing`);
    }
    return value;
};

const formatHexBytes16 = (bytes: Uint8Array): string => {
    if (bytes.length < 16) {
        throw new Error(`Expected at least 16 bytes for ID formatting, got ${bytes.length}`);
    }
    const hex = HEX_TABLE;
    let out = '';
    for (let index = 0; index < 16; index += 1) {
        const byteValue = requireByte(bytes, index, 'ID');
        out += requireHexPart(hex, byteValue);
    }
    return out;
};

const formatUuid = (bytes: Uint8Array): string => {
    const hex = formatHexBytes16(bytes);
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

const normalizePrefix = (prefix: string | null): string | null => {
    if (prefix === null) {
        return null;
    }
    const trimmed = prefix.trim();
    return trimmed ? trimmed : null;
};

const formatHex = (bytes: Uint8Array): string => formatHexBytes16(bytes);

interface IdGeneratorOptions {
    prefix?: string | null;
    format?: 'uuid' | 'hex';
    separator?: string;
}

interface NormalizedOptions {
    prefix: string | null;
    format: 'uuid' | 'hex';
    separator: string;
}

const normalizeOptions = (input: string | IdGeneratorOptions | null | undefined): NormalizedOptions => {
    if (isString(input)) {
        return { prefix: normalizePrefix(input), format: 'uuid', separator: '-' };
    }
    if (isObject(input)) {
        const { prefix = null, format = 'uuid', separator = '-' } = input;
        const normalizedFormat = isString(format) ? format.trim().toLowerCase() : '';
        return {
            prefix: normalizePrefix(isString(prefix) ? prefix : null),
            format: normalizedFormat === 'hex' ? 'hex' : 'uuid',
            separator: isString(separator) ? separator.trim() : '-'
        };
    }
    return { prefix: null, format: 'uuid', separator: '-' };
};

const generateSecureId = (options: string | IdGeneratorOptions | null = null): string => {
    const cryptoApi = ensureCrypto();
    const buffer = new Uint8Array(16);
    cryptoApi.getRandomValues(buffer);
    const versionByte = requireByte(buffer, 6, 'UUID');
    buffer[6] = (versionByte & 0x0f) | 0x40;
    const variantByte = requireByte(buffer, 8, 'UUID');
    buffer[8] = (variantByte & 0x3f) | 0x80;
    const { prefix, format, separator } = normalizeOptions(options);
    const base = format && format.toLowerCase() === 'hex' ? formatHex(buffer) : formatUuid(buffer);
    if (!prefix) return base;
    const sep = separator || '';
    return sep ? `${prefix}${sep}${base}` : `${prefix}${base}`;
};

export { generateSecureId };

export type { IdGeneratorOptions };
