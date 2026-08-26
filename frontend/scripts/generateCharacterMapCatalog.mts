#!/usr/bin/env node
/* SoAI - Frontend character map catalog generator [frontend/scripts/generateCharacterMapCatalog.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { randomUUID } from 'node:crypto';
import { closeSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { format, resolveConfig } from 'prettier';
import { decodeCharacterMapCatalog } from '../assets/ts/features/chat/charactermap/catalogDecoder.ts';
import type { JsonValue } from '../assets/ts/core/types/jsonValues.ts';
import { decodeCanonicalSource, parseBlocks, parseDerivedNames, parseEmoji, type UnicodeSourceName } from './characterMapCatalog/sourceParsing.mts';

const projectRoot = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const unicodeSourceRoot = path.join(projectRoot, 'vendor', 'unicode', '17.0.0');
const outputPath = path.join(projectRoot, 'assets', 'unicode', 'character-map.json');

const readSource = (sourceName: UnicodeSourceName, sourcePath: string): string => decodeCanonicalSource(readFileSync(sourcePath), sourceName);

const buildCatalog = (): JsonValue => ({
    schemaVersion: 1,
    unicodeVersion: '17.0.0',
    license: 'Unicode-3.0',
    licensePath: 'unicode/LICENSE.txt',
    nameRecords: parseDerivedNames(readSource('DerivedName.txt', path.join(unicodeSourceRoot, 'DerivedName.txt'))),
    blocks: parseBlocks(readSource('Blocks.txt', path.join(unicodeSourceRoot, 'Blocks.txt'))),
    emoji: parseEmoji(readSource('emoji-test.txt', path.join(unicodeSourceRoot, 'emoji-test.txt')))
});

const writeCatalogAtomically = (serialized: string): void => {
    const temporaryPath = `${outputPath}.${process.pid}-${randomUUID()}.tmp`;
    let descriptor: number | null = null;
    try {
        descriptor = openSync(temporaryPath, 'wx');
        writeFileSync(descriptor, serialized, 'utf8');
        closeSync(descriptor);
        descriptor = null;
        const staged = JSON.parse(readFileSync(temporaryPath, 'utf8'));
        decodeCharacterMapCatalog(staged);
        renameSync(temporaryPath, outputPath);
    } finally {
        if (descriptor !== null) closeSync(descriptor);
        try {
            unlinkSync(temporaryPath);
        } catch (error) {
            if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
        }
    }
};

const generateCharacterMapCatalog = async (): Promise<void> => {
    decodeCanonicalSource(readFileSync(path.join(projectRoot, 'assets', 'unicode', 'LICENSE.txt')), 'LICENSE.txt');
    const candidate = buildCatalog();
    decodeCharacterMapCatalog(candidate);
    const prettierConfig = await resolveConfig(outputPath);
    if (prettierConfig === null) throw new Error('Character-map catalog generation requires the frontend Prettier configuration');
    writeCatalogAtomically(await format(JSON.stringify(candidate), { ...prettierConfig, parser: 'json' }));
};

const isDirectExecution = (): boolean => {
    const entryPath = process.argv[1];
    return entryPath !== undefined && path.resolve(entryPath) === fileURLToPath(import.meta.url);
};

if (isDirectExecution()) await generateCharacterMapCatalog();

export { generateCharacterMapCatalog };
