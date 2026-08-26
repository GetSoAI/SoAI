#!/usr/bin/env node
/* SoAI - Frontend character map Unicode source parsing [frontend/scripts/characterMapCatalog/sourceParsing.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHash } from 'node:crypto';
import type { CharacterMapBlock, CharacterMapEmojiRecord, CharacterMapEmojiStatus, CharacterMapNameRecord } from '../../assets/ts/features/chat/charactermap/catalogContracts.ts';

type UnicodeSourceName = 'DerivedName.txt' | 'Blocks.txt' | 'emoji-test.txt' | 'LICENSE.txt';

const SOURCE_HASHES: Readonly<Record<UnicodeSourceName, string>> = Object.freeze({
    'DerivedName.txt': '019758bbe6c756c40fca6d505187ea660c5e195533e2ff2c841963a212c9d369',
    'Blocks.txt': 'c0edefaf1a19771e830a82735472716af6bf3c3975f6c2a23ffbe2580fbbcb15',
    'emoji-test.txt': '1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda',
    'LICENSE.txt': 'e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96'
});

const decodeCanonicalSource = (bytes: Uint8Array, sourceName: UnicodeSourceName): string => {
    let decoded: string;
    try {
        decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch {
        throw new Error(`${sourceName} is not valid UTF-8`);
    }
    if (decoded.replace(/\r\n/g, '').includes('\r')) throw new Error(`${sourceName} contains a bare carriage return`);
    const canonical = decoded.replace(/\r\n/g, '\n');
    const digest = createHash('sha256').update(canonical, 'utf8').digest('hex');
    if (digest !== SOURCE_HASHES[sourceName]) throw new Error(`${sourceName} SHA-256 does not match the pinned Unicode source`);
    return canonical;
};

const parseScalar = (value: string, label: string): number => {
    if (!/^[0-9A-F]{4,6}$/u.test(value)) throw new Error(`${label} has an invalid code point`);
    return Number.parseInt(value, 16);
};

const parseDerivedNames = (source: string): readonly CharacterMapNameRecord[] => {
    if (!source.startsWith('# DerivedName-17.0.0.txt\n')) throw new Error('DerivedName.txt has an unexpected version header');
    const records: CharacterMapNameRecord[] = [];
    for (const [lineIndex, line] of source.split('\n').entries()) {
        if (line.length === 0 || line.startsWith('#')) continue;
        const match = /^([0-9A-F]{4,6})(?:\.\.([0-9A-F]{4,6}))?\s+;\s+(.+)$/u.exec(line);
        if (match === null) throw new Error(`DerivedName.txt line ${lineIndex + 1} is malformed`);
        const startText = match[1];
        const endText = match[2];
        const name = match[3];
        if (startText === undefined || name === undefined) throw new Error(`DerivedName.txt line ${lineIndex + 1} is incomplete`);
        const start = parseScalar(startText, `DerivedName.txt line ${lineIndex + 1}`);
        const end = endText === undefined ? start : parseScalar(endText, `DerivedName.txt line ${lineIndex + 1}`);
        records.push(Object.freeze([start, end, name]));
    }
    return Object.freeze(records);
};

const parseBlocks = (source: string): readonly CharacterMapBlock[] => {
    if (!source.startsWith('# Blocks-17.0.0.txt\n')) throw new Error('Blocks.txt has an unexpected version header');
    const blocks: CharacterMapBlock[] = [];
    for (const [lineIndex, line] of source.split('\n').entries()) {
        if (line.length === 0 || line.startsWith('#')) continue;
        const match = /^([0-9A-F]{4,6})\.\.([0-9A-F]{4,6});\s+(.+)$/u.exec(line);
        if (match === null) throw new Error(`Blocks.txt line ${lineIndex + 1} is malformed`);
        const startText = match[1];
        const endText = match[2];
        const name = match[3];
        if (startText === undefined || endText === undefined || name === undefined) throw new Error(`Blocks.txt line ${lineIndex + 1} is incomplete`);
        blocks.push(Object.freeze([parseScalar(startText, `Blocks.txt line ${lineIndex + 1}`), parseScalar(endText, `Blocks.txt line ${lineIndex + 1}`), name]));
    }
    return Object.freeze(blocks);
};

const parseEmojiStatus = (value: string, lineNumber: number): CharacterMapEmojiStatus | null => {
    if (value === 'fully-qualified' || value === 'component') return value;
    if (value === 'minimally-qualified' || value === 'unqualified') return null;
    throw new Error(`emoji-test.txt line ${lineNumber} has an unsupported status`);
};

const parseEmoji = (source: string): readonly CharacterMapEmojiRecord[] => {
    if (!source.includes('\n# Version: 17.0\n')) throw new Error('emoji-test.txt has an unexpected version header');
    const records: CharacterMapEmojiRecord[] = [];
    let group = '';
    let subgroup = '';
    for (const [lineIndex, line] of source.split('\n').entries()) {
        const groupMatch = /^# group: (.+)$/u.exec(line);
        if (groupMatch?.[1] !== undefined) {
            group = groupMatch[1];
            subgroup = '';
            continue;
        }
        const subgroupMatch = /^# subgroup: (.+)$/u.exec(line);
        if (subgroupMatch?.[1] !== undefined) {
            subgroup = subgroupMatch[1];
            continue;
        }
        if (line.length === 0 || line.startsWith('#')) continue;
        const match = /^([0-9A-F ]+)\s+;\s+([a-z-]+)\s+#\s+.+?\s+E\d+\.\d+\s+(.+)$/u.exec(line);
        if (match === null) throw new Error(`emoji-test.txt line ${lineIndex + 1} is malformed`);
        const codePointText = match[1];
        const statusText = match[2];
        const name = match[3];
        if (codePointText === undefined || statusText === undefined || name === undefined) throw new Error(`emoji-test.txt line ${lineIndex + 1} is incomplete`);
        const status = parseEmojiStatus(statusText, lineIndex + 1);
        if (status === null) continue;
        if (group.length === 0 || subgroup.length === 0) throw new Error(`emoji-test.txt line ${lineIndex + 1} has no group context`);
        const codePoints = Object.freeze(
            codePointText
                .trim()
                .split(/ +/u)
                .map((codePoint) => parseScalar(codePoint, `emoji-test.txt line ${lineIndex + 1}`))
        );
        records.push(Object.freeze([codePoints, status, name, group, subgroup]));
    }
    return Object.freeze(records);
};

export { decodeCanonicalSource, parseBlocks, parseDerivedNames, parseEmoji };
export type { UnicodeSourceName };
