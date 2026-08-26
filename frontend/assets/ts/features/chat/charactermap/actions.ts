/* SoAI - Frontend chat character map modal actions [frontend/assets/ts/features/chat/charactermap/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const CHARACTER_MAP_ACTIONS = Object.freeze({
    SEARCH: 'character-map:search',
    RETRY: 'character-map:retry',
    ACTIVATE_RESULT: 'character-map:activate-result',
    SELECT: 'character-map:select',
    COPY: 'character-map:copy',
    INSERT: 'character-map:insert'
});

type CharacterMapAction = (typeof CHARACTER_MAP_ACTIONS)[keyof typeof CHARACTER_MAP_ACTIONS];

const { guard: isCharacterMapAction } = createActionIdSet<CharacterMapAction>(...Object.values(CHARACTER_MAP_ACTIONS));

export { CHARACTER_MAP_ACTIONS, isCharacterMapAction };
export type { CharacterMapAction };
