/* SoAI - Prompts page support [frontend/assets/ts/pages/prompts/contracts/PromptsPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { promptsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { normalizeCollectionPromptId } from '@pages/prompts/controllers/page/state.ts';

const PAGE_ID = 'prompts';
const DEFAULT_SORT = 'none';
const PROMPT_CARD_SELECTOR = promptsPageConfig.grid.cardSelector;
const COLLECTION_OPTIONS = Object.freeze({ normalizeId: normalizeCollectionPromptId });

export { PAGE_ID, DEFAULT_SORT, PROMPT_CARD_SELECTOR, COLLECTION_OPTIONS };
