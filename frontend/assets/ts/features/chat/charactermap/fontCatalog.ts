/* SoAI - Frontend chat character map curated font catalog [frontend/assets/ts/features/chat/charactermap/fontCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type CharacterMapFontId = 'soai-sans' | 'soai-mono' | 'serif' | 'sans-serif' | 'monospace' | 'symbols' | 'emoji';

type CharacterMapFont = Readonly<{
    id: CharacterMapFontId;
    className: string;
}>;

const CHARACTER_MAP_FONTS: readonly CharacterMapFont[] = Object.freeze([Object.freeze({ id: 'soai-sans', className: 'chat-character-map-font--soai-sans' }), Object.freeze({ id: 'soai-mono', className: 'chat-character-map-font--soai-mono' }), Object.freeze({ id: 'serif', className: 'chat-character-map-font--serif' }), Object.freeze({ id: 'sans-serif', className: 'chat-character-map-font--sans-serif' }), Object.freeze({ id: 'monospace', className: 'chat-character-map-font--monospace' }), Object.freeze({ id: 'symbols', className: 'chat-character-map-font--symbols' }), Object.freeze({ id: 'emoji', className: 'chat-character-map-font--emoji' })]);

const CHARACTER_MAP_DEFAULT_FONT_ID: CharacterMapFontId = 'soai-sans';
const CHARACTER_MAP_FONT_CLASSES: readonly string[] = Object.freeze(CHARACTER_MAP_FONTS.map((font) => font.className));

const getCharacterMapFont = (value: string): CharacterMapFont => {
    const font = CHARACTER_MAP_FONTS.find((candidate) => candidate.id === value);
    if (font === undefined) throw new Error('Unknown character-map font');
    return font;
};

const isCharacterMapFontId = (value: string): value is CharacterMapFontId => CHARACTER_MAP_FONTS.some((font) => font.id === value);

export { CHARACTER_MAP_DEFAULT_FONT_ID, CHARACTER_MAP_FONT_CLASSES, CHARACTER_MAP_FONTS, getCharacterMapFont, isCharacterMapFontId };
export type { CharacterMapFont, CharacterMapFontId };
