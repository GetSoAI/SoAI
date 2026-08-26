/* SoAI - Frontend chat character map catalog decoder [frontend/assets/ts/features/chat/charactermap/catalogDecoder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isUnicodeScalarText } from '@core/primitives/text.ts';
import { isFiniteInteger } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { CharacterMapBlock, CharacterMapCatalog, CharacterMapEmojiRecord, CharacterMapEmojiStatus, CharacterMapNameRecord } from '@features/chat/charactermap/catalogContracts.ts';

const ROOT_KEYS = Object.freeze(['blocks', 'emoji', 'license', 'licensePath', 'nameRecords', 'schemaVersion', 'unicodeVersion']);
const MAXIMUM_CODE_POINT = 0x10ffff;
const EXPECTED_NAME_RECORDS = 45_784;
const EXPECTED_NAME_SCALARS = 159_801;
const EXPECTED_BLOCKS = 346;
const EXPECTED_EMOJI = 3_953;
const EXPECTED_FULLY_QUALIFIED_EMOJI = 3_944;
const EXPECTED_COMPONENT_EMOJI = 9;
const EXPECTED_EMOJI_GROUPS = 10;
const EXPECTED_EMOJI_SUBGROUPS = 100;

function fail(message: string): never {
    throw new Error(`Invalid Unicode character-map catalog: ${message}`);
}

const requireExactKeys = (value: JsonObject, keys: readonly string[], label: string): void => {
    const actualKeys = Object.keys(value).sort((left, right) => left.localeCompare(right, 'en'));
    if (actualKeys.length !== keys.length || actualKeys.some((key, index) => key !== keys[index])) fail(`${label} has unexpected keys`);
};

const isScalar = (value: JsonValue): value is number => typeof value === 'number' && isFiniteInteger(value) && value >= 0 && value <= MAXIMUM_CODE_POINT && !(value >= 0xd800 && value <= 0xdfff);
const isCodePoint = (value: JsonValue): value is number => typeof value === 'number' && isFiniteInteger(value) && value >= 0 && value <= MAXIMUM_CODE_POINT;

const requireArrayItem = (value: readonly JsonValue[], index: number, label: string): JsonValue => {
    const item = value[index];
    if (item === undefined) fail(`${label} is missing`);
    return item;
};

const requireProperty = (value: JsonObject, key: string): JsonValue => {
    const property = value[key];
    if (property === undefined) fail(`root property ${key} is missing`);
    return property;
};

const requireText = (value: JsonValue, label: string): string => {
    if (typeof value !== 'string' || value.length === 0 || value.trim() !== value || !isUnicodeScalarText(value)) fail(`${label} must be non-empty Unicode scalar text`);
    return value;
};

const requireInterval = (value: JsonValue, label: string): readonly [number, number, string] => {
    if (!isJsonArray(value) || value.length !== 3) fail(`${label} must be a three-item tuple`);
    const start = requireArrayItem(value, 0, label);
    const end = requireArrayItem(value, 1, label);
    const name = requireArrayItem(value, 2, label);
    if (!isCodePoint(start) || !isCodePoint(end) || start > end) fail(`${label} has an invalid code-point interval`);
    return Object.freeze([start, end, requireText(name, `${label} name`)]);
};

const decodeNames = (value: JsonValue): readonly CharacterMapNameRecord[] => {
    if (!isJsonArray(value) || value.length !== EXPECTED_NAME_RECORDS) fail(`nameRecords must contain ${EXPECTED_NAME_RECORDS} records`);
    const records: CharacterMapNameRecord[] = [];
    let previousEnd = -1;
    let scalarCount = 0;
    let rangeCount = 0;
    for (const [index, candidate] of value.entries()) {
        const record = requireInterval(candidate, `nameRecords[${index}]`);
        if (!isScalar(record[0]) || !isScalar(record[1])) fail(`nameRecords[${index}] has a non-scalar boundary`);
        if (record[0] <= 0xdfff && record[1] >= 0xd800) fail(`nameRecords[${index}] crosses the surrogate range`);
        if (record[0] <= previousEnd) fail('nameRecords must be sorted and non-overlapping');
        const placeholderCount = record[2].split('*').length - 1;
        if (placeholderCount > 1 || (record[0] !== record[1] && placeholderCount !== 1)) fail(`nameRecords[${index}] has an invalid name template`);
        if (record[0] !== record[1]) rangeCount += 1;
        scalarCount += record[1] - record[0] + 1;
        previousEnd = record[1];
        records.push(record);
    }
    if (rangeCount !== 17 || scalarCount !== EXPECTED_NAME_SCALARS) fail('nameRecords expansion counts do not match Unicode 17.0.0');
    return Object.freeze(records);
};

const decodeBlocks = (value: JsonValue): readonly CharacterMapBlock[] => {
    if (!isJsonArray(value) || value.length !== EXPECTED_BLOCKS) fail(`blocks must contain ${EXPECTED_BLOCKS} records`);
    const blocks: CharacterMapBlock[] = [];
    let previousEnd = -1;
    let hasBasicLatin = false;
    for (const [index, candidate] of value.entries()) {
        const block = requireInterval(candidate, `blocks[${index}]`);
        if (block[0] <= previousEnd) fail('blocks must be sorted and non-overlapping');
        if (block[0] === 0 && block[1] === 0x7f && block[2] === 'Basic Latin') hasBasicLatin = true;
        previousEnd = block[1];
        blocks.push(block);
    }
    if (!hasBasicLatin) fail('blocks must contain Basic Latin');
    return Object.freeze(blocks);
};

const requireEmojiStatus = (value: JsonValue, label: string): CharacterMapEmojiStatus => {
    if (value !== 'fully-qualified' && value !== 'component') fail(`${label} has an unsupported status`);
    return value;
};

const decodeCodePoints = (value: JsonValue, label: string): readonly number[] => {
    if (!isJsonArray(value) || value.length === 0 || !value.every(isScalar)) fail(`${label} must contain Unicode scalars`);
    return Object.freeze([...value]);
};

const decodeEmojiRecord = (value: JsonValue, index: number): CharacterMapEmojiRecord => {
    if (!isJsonArray(value) || value.length !== 5) fail(`emoji[${index}] must be a five-item tuple`);
    return Object.freeze([decodeCodePoints(requireArrayItem(value, 0, `emoji[${index}]`), `emoji[${index}] code points`), requireEmojiStatus(requireArrayItem(value, 1, `emoji[${index}]`), `emoji[${index}]`), requireText(requireArrayItem(value, 2, `emoji[${index}]`), `emoji[${index}] name`), requireText(requireArrayItem(value, 3, `emoji[${index}]`), `emoji[${index}] group`), requireText(requireArrayItem(value, 4, `emoji[${index}]`), `emoji[${index}] subgroup`)]);
};

const decodeEmoji = (value: JsonValue): readonly CharacterMapEmojiRecord[] => {
    if (!isJsonArray(value) || value.length !== EXPECTED_EMOJI) fail(`emoji must contain ${EXPECTED_EMOJI} records`);
    const records: CharacterMapEmojiRecord[] = [];
    const sequences = new Set<string>();
    const groups = new Set<string>();
    const subgroups = new Set<string>();
    let fullyQualifiedCount = 0;
    for (const [index, candidate] of value.entries()) {
        const record = decodeEmojiRecord(candidate, index);
        const sequenceKey = record[0].join('-');
        if (sequences.has(sequenceKey)) fail(`emoji[${index}] duplicates a sequence`);
        sequences.add(sequenceKey);
        groups.add(record[3]);
        subgroups.add(`${record[3]}\u0000${record[4]}`);
        if (record[1] === 'fully-qualified') fullyQualifiedCount += 1;
        records.push(record);
    }
    if (fullyQualifiedCount !== EXPECTED_FULLY_QUALIFIED_EMOJI || records.length - fullyQualifiedCount !== EXPECTED_COMPONENT_EMOJI) fail('emoji status counts do not match Unicode 17.0');
    if (groups.size !== EXPECTED_EMOJI_GROUPS || subgroups.size !== EXPECTED_EMOJI_SUBGROUPS) fail('emoji group counts do not match Unicode 17.0');
    return Object.freeze(records);
};

const decodeCharacterMapCatalog = (value: JsonValue): CharacterMapCatalog => {
    if (!isJsonObject(value)) fail('root must be an object');
    requireExactKeys(value, ROOT_KEYS, 'root');
    if (requireProperty(value, 'schemaVersion') !== 1 || requireProperty(value, 'unicodeVersion') !== '17.0.0' || requireProperty(value, 'license') !== 'Unicode-3.0' || requireProperty(value, 'licensePath') !== 'unicode/LICENSE.txt') fail('root metadata does not match the V1 Unicode 17.0.0 contract');
    const catalog: CharacterMapCatalog = {
        schemaVersion: 1,
        unicodeVersion: '17.0.0',
        license: 'Unicode-3.0',
        licensePath: 'unicode/LICENSE.txt',
        nameRecords: decodeNames(requireProperty(value, 'nameRecords')),
        blocks: decodeBlocks(requireProperty(value, 'blocks')),
        emoji: decodeEmoji(requireProperty(value, 'emoji'))
    };
    return Object.freeze(catalog);
};

export { decodeCharacterMapCatalog };
