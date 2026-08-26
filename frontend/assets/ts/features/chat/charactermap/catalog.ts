/* SoAI - Frontend chat character map catalog query domain [frontend/assets/ts/features/chat/charactermap/catalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CharacterMapBlock, CharacterMapCatalog, CharacterMapEmojiRecord, CharacterMapNameRecord } from '@features/chat/charactermap/catalogContracts.ts';

type CharacterMapSelectorType = 'unicode-all' | 'unicode-block' | 'emoji-all' | 'emoji-group';

type CharacterMapSelector = Readonly<{
    id: string;
    type: CharacterMapSelectorType;
    label: string;
    blockIndex: number | null;
    emojiGroup: string | null;
}>;

type CharacterMapResultItem = Readonly<{
    id: string;
    text: string;
    codePoints: readonly number[];
    codePointText: string;
    name: string;
}>;

type CharacterMapQueryResult = Readonly<{
    ids: readonly string[];
    lookup: ReadonlyMap<string, CharacterMapResultItem>;
}>;

const ALL_UNICODE_SELECTOR_ID = 'unicode:all';
const ALL_EMOJI_SELECTOR_ID = 'emoji:all';

const formatCodePoint = (codePoint: number): string => `U+${codePoint.toString(16).toUpperCase().padStart(4, '0')}`;
const formatCodePoints = (codePoints: readonly number[]): string => codePoints.map(formatCodePoint).join(' ');

const expandName = (record: CharacterMapNameRecord, codePoint: number): string => record[2].replace('*', codePoint.toString(16).toUpperCase().padStart(4, '0'));

const normalizeSearch = (value: string): string => value.trim().replace(/\s+/gu, ' ').toUpperCase();

const matchesSearch = (item: CharacterMapResultItem, search: string): boolean => {
    if (search.length === 0) return true;
    const plainCodePoints = item.codePoints.map((codePoint) => codePoint.toString(16).toUpperCase().padStart(4, '0')).join(' ');
    return item.name.toUpperCase().includes(search) || item.codePointText.includes(search) || plainCodePoints.includes(search);
};

const createUnicodeItem = (record: CharacterMapNameRecord, codePoint: number): CharacterMapResultItem => {
    const codePoints = Object.freeze([codePoint]);
    return Object.freeze({ id: `u-${codePoint.toString(16).toUpperCase()}`, text: String.fromCodePoint(codePoint), codePoints, codePointText: formatCodePoints(codePoints), name: expandName(record, codePoint) });
};

const createEmojiItem = (record: CharacterMapEmojiRecord, index: number): CharacterMapResultItem => Object.freeze({ id: `e-${index}`, text: String.fromCodePoint(...record[0]), codePoints: record[0], codePointText: formatCodePoints(record[0]), name: record[2] });

const appendItem = (item: CharacterMapResultItem, search: string, ids: string[], lookup: Map<string, CharacterMapResultItem>): void => {
    if (!matchesSearch(item, search)) return;
    ids.push(item.id);
    lookup.set(item.id, item);
};

const enumerateUnicode = (records: readonly CharacterMapNameRecord[], interval: readonly [number, number] | null, search: string, ids: string[], lookup: Map<string, CharacterMapResultItem>): void => {
    for (const record of records) {
        const start = interval === null ? record[0] : Math.max(record[0], interval[0]);
        const end = interval === null ? record[1] : Math.min(record[1], interval[1]);
        if (start > end) continue;
        for (let codePoint = start; codePoint <= end; codePoint += 1) appendItem(createUnicodeItem(record, codePoint), search, ids, lookup);
    }
};

const enumerateEmoji = (records: readonly CharacterMapEmojiRecord[], group: string | null, search: string, ids: string[], lookup: Map<string, CharacterMapResultItem>): void => {
    for (const [index, record] of records.entries()) {
        if (group !== null && record[3] !== group) continue;
        appendItem(createEmojiItem(record, index), search, ids, lookup);
    }
};

const createSelector = (id: string, type: CharacterMapSelectorType, label: string, blockIndex: number | null, emojiGroup: string | null): CharacterMapSelector => Object.freeze({ id, type, label, blockIndex, emojiGroup });

const createSelectors = (catalog: CharacterMapCatalog): readonly CharacterMapSelector[] => {
    const selectors: CharacterMapSelector[] = [createSelector(ALL_UNICODE_SELECTOR_ID, 'unicode-all', '', null, null), createSelector(ALL_EMOJI_SELECTOR_ID, 'emoji-all', '', null, null)];
    for (const [index, block] of catalog.blocks.entries()) selectors.push(createSelector(`unicode:block:${index}`, 'unicode-block', block[2], index, null));
    const groups = new Set<string>();
    for (const emoji of catalog.emoji) {
        if (groups.has(emoji[3])) continue;
        groups.add(emoji[3]);
        selectors.push(createSelector(`emoji:group:${groups.size - 1}`, 'emoji-group', emoji[3], null, emoji[3]));
    }
    return Object.freeze(selectors);
};

const requireBlock = (catalog: CharacterMapCatalog, index: number | null): CharacterMapBlock => {
    const block = index === null ? undefined : catalog.blocks[index];
    if (block === undefined) throw new Error('Character-map selector references an unknown Unicode block');
    return block;
};

class CharacterMapCatalogIndex {
    readonly #catalog: CharacterMapCatalog;
    readonly #selectors: readonly CharacterMapSelector[];
    readonly #selectorById: ReadonlyMap<string, CharacterMapSelector>;
    readonly #defaultSelectorId: string;

    constructor(catalog: CharacterMapCatalog) {
        this.#catalog = catalog;
        this.#selectors = createSelectors(catalog);
        this.#selectorById = new Map(this.#selectors.map((selector) => [selector.id, selector]));
        const defaultSelector = this.#selectors.find((selector) => selector.type === 'unicode-block' && selector.label === 'Basic Latin');
        if (defaultSelector === undefined) throw new Error('Character-map catalog has no Basic Latin selector');
        this.#defaultSelectorId = defaultSelector.id;
    }

    get selectors(): readonly CharacterMapSelector[] {
        return this.#selectors;
    }

    get defaultSelectorId(): string {
        return this.#defaultSelectorId;
    }

    isSelectorId(value: string): boolean {
        return this.#selectorById.has(value);
    }

    query(selectorId: string, searchText: string): CharacterMapQueryResult {
        const selector = this.#selectorById.get(selectorId);
        if (selector === undefined) throw new Error('Unknown character-map selector');
        const search = normalizeSearch(searchText);
        const ids: string[] = [];
        const lookup = new Map<string, CharacterMapResultItem>();
        if (selector.type === 'unicode-all') enumerateUnicode(this.#catalog.nameRecords, null, search, ids, lookup);
        if (selector.type === 'unicode-block') {
            const block = requireBlock(this.#catalog, selector.blockIndex);
            enumerateUnicode(this.#catalog.nameRecords, [block[0], block[1]], search, ids, lookup);
        }
        if (selector.type === 'emoji-all') enumerateEmoji(this.#catalog.emoji, null, search, ids, lookup);
        if (selector.type === 'emoji-group') enumerateEmoji(this.#catalog.emoji, selector.emojiGroup, search, ids, lookup);
        return Object.freeze({ ids: Object.freeze(ids), lookup });
    }
}

export { ALL_EMOJI_SELECTOR_ID, ALL_UNICODE_SELECTOR_ID, CharacterMapCatalogIndex, formatCodePoint, formatCodePoints };
export type { CharacterMapQueryResult, CharacterMapResultItem, CharacterMapSelector, CharacterMapSelectorType };
