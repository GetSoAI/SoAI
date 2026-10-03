/* SoAI - Build-time startup recovery translation extraction [frontend/build/bootMessages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { BOOT_MESSAGE_KEYS, type BootMessageCatalog } from '../assets/ts/core/languageservice/bootMessageCatalog.ts';
import { isObject, normalizeTranslations, type JsonValue } from '../scripts/translationKeyCatalog.mts';

const readCatalog = (filename: string): JsonValue => JSON.parse(readFileSync(filename, 'utf8'));

const buildBootMessages = (frontendRoot: string): BootMessageCatalog => {
    const directory = path.join(frontendRoot, 'assets/lang');
    const manifest = readCatalog(path.join(directory, 'manifest.json'));
    if (!isObject(manifest) || typeof manifest['defaultLanguage'] !== 'string' || !Array.isArray(manifest['languages'])) throw new Error('Startup translation manifest is invalid');
    const locales = manifest['languages'].map((locale): BootMessageCatalog['locales'][number] => {
        if (!isObject(locale) || typeof locale['code'] !== 'string' || (locale['direction'] !== 'ltr' && locale['direction'] !== 'rtl')) throw new Error('Startup translation locale is invalid');
        const code = locale['code'];
        const catalog = readCatalog(path.join(directory, `${code}.json`));
        if (!isObject(catalog) || catalog['translations'] === undefined) throw new Error(`Startup translation catalog is invalid: ${code}`);
        const translations = normalizeTranslations(catalog['translations']);
        const messages: Record<string, string> = {};
        for (const key of BOOT_MESSAGE_KEYS) {
            let value: JsonValue | undefined = translations;
            for (const segment of key.split('.')) value = value !== undefined && isObject(value) ? value[segment] : undefined;
            if (typeof value !== 'string' || !value.trim()) throw new Error(`Startup translation missing: ${code}:${key}`);
            messages[key] = value;
        }
        return { code, direction: locale['direction'], messages };
    });
    if (!locales.some((locale) => locale.code === manifest['defaultLanguage'])) throw new Error('Startup default locale is missing');
    return { defaultLanguage: manifest['defaultLanguage'], locales };
};

export { buildBootMessages };
