/* SoAI - Search page actions [frontend/assets/ts/pages/search/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export const SEARCH_ACTION_CLEAR_RECENT = 'search.clearRecent';
export const SEARCH_ACTION_SELECT_RECENT = 'search.selectRecent';
export const SEARCH_ACTION_OPEN_ITEM = 'search.openItem';

export type SearchActionId = typeof SEARCH_ACTION_CLEAR_RECENT | typeof SEARCH_ACTION_SELECT_RECENT | typeof SEARCH_ACTION_OPEN_ITEM;

const { guard: isSearchActionId } = createActionIdSet(SEARCH_ACTION_CLEAR_RECENT, SEARCH_ACTION_SELECT_RECENT, SEARCH_ACTION_OPEN_ITEM);

export { isSearchActionId };
