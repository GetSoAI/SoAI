/* SoAI - Character map persisted view state [frontend/assets/ts/pages/chat/controllers/modals/charactermap/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isCharacterMapFontId, type CharacterMapFontId } from '@features/chat/public.ts';

const CHARACTER_MAP_VIEW_STATE_STORAGE_KEY = 'chat_character_map_view_state';
const VIEW_STATE_KEYS = Object.freeze(['anchor', 'fontId', 'schemaVersion', 'selectorId']);
const ANCHOR_KEYS = Object.freeze(['atStart', 'identifier', 'offset']);

interface CharacterMapViewStateStorage {
    get(key: string, defaultValue?: JsonValue | null): JsonValue | null;
    set(key: string, value: JsonValue | null): void;
}

interface CharacterMapViewState {
    fontId: CharacterMapFontId;
    selectorId: string;
    anchor: CollectionViewportAnchor | null;
}

const hasExactKeys = (value: JsonObject, keys: readonly string[]): boolean => {
    const actual = Object.keys(value).sort((left, right) => left.localeCompare(right, 'en'));
    return actual.length === keys.length && actual.every((key, index) => key === keys[index]);
};

const decodeAnchor = (value: JsonValue | undefined): CollectionViewportAnchor | null | undefined => {
    if (value === null) return null;
    if (!isJsonObject(value) || !hasExactKeys(value, ANCHOR_KEYS)) return undefined;
    const identifier = value['identifier'];
    const offset = value['offset'];
    const atStart = value['atStart'];
    if (typeof identifier !== 'string' || identifier.length === 0 || !isFiniteNumber(offset) || typeof atStart !== 'boolean') return undefined;
    return { identifier, offset, atStart };
};

const decodeCharacterMapViewState = (value: JsonValue | null): CharacterMapViewState | null => {
    if (!isJsonObject(value) || !hasExactKeys(value, VIEW_STATE_KEYS) || value['schemaVersion'] !== 1) return null;
    const fontId = value['fontId'];
    const selectorId = value['selectorId'];
    const anchor = decodeAnchor(value['anchor']);
    if (typeof fontId !== 'string' || !isCharacterMapFontId(fontId) || typeof selectorId !== 'string' || selectorId.length === 0 || anchor === undefined) return null;
    return { fontId, selectorId, anchor };
};

const readCharacterMapViewState = (storage: CharacterMapViewStateStorage): CharacterMapViewState | null => decodeCharacterMapViewState(storage.get(CHARACTER_MAP_VIEW_STATE_STORAGE_KEY, null));

const writeCharacterMapViewState = (storage: CharacterMapViewStateStorage, state: CharacterMapViewState): void => {
    storage.set(CHARACTER_MAP_VIEW_STATE_STORAGE_KEY, {
        schemaVersion: 1,
        fontId: state.fontId,
        selectorId: state.selectorId,
        anchor: state.anchor === null ? null : { identifier: state.anchor.identifier, offset: state.anchor.offset, atStart: state.anchor.atStart }
    });
};

export { decodeCharacterMapViewState, readCharacterMapViewState, writeCharacterMapViewState };
export type { CharacterMapViewState, CharacterMapViewStateStorage };
