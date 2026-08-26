/* SoAI - Frontend chat character map catalog contracts [frontend/assets/ts/features/chat/charactermap/catalogContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type CharacterMapNameRecord = readonly [start: number, end: number, name: string];
type CharacterMapBlock = readonly [start: number, end: number, name: string];
type CharacterMapEmojiStatus = 'fully-qualified' | 'component';
type CharacterMapEmojiRecord = readonly [codePoints: readonly number[], status: CharacterMapEmojiStatus, name: string, group: string, subgroup: string];

type CharacterMapCatalog = Readonly<{
    schemaVersion: 1;
    unicodeVersion: '17.0.0';
    license: 'Unicode-3.0';
    licensePath: 'unicode/LICENSE.txt';
    nameRecords: readonly CharacterMapNameRecord[];
    blocks: readonly CharacterMapBlock[];
    emoji: readonly CharacterMapEmojiRecord[];
}>;

export type { CharacterMapBlock, CharacterMapCatalog, CharacterMapEmojiRecord, CharacterMapEmojiStatus, CharacterMapNameRecord };
