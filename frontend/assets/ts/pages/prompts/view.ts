/* SoAI - Prompts page rendering [frontend/assets/ts/pages/prompts/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BuildConfig } from '@core/uiprimitives/types.ts';
import { buildPromptsHeader } from '@pages/prompts/rendering/header.ts';
import type { PromptsLayoutBuildDependencies } from '@pages/prompts/rendering/internalContracts.ts';
import { buildPromptsSections } from '@pages/prompts/rendering/sections.ts';

const buildPromptsLayoutConfig = ({ getIconSync, sortBy, sortOrder, onSortChange }: PromptsLayoutBuildDependencies): BuildConfig => {
    return {
        header: buildPromptsHeader(getIconSync, sortBy, sortOrder),
        sections: buildPromptsSections(sortBy, sortOrder),
        filters: {},
        actions: [{ selector: '#prompts-sort', event: 'change', handler: onSortChange }],
        delegated: []
    };
};

export { buildPromptsLayoutConfig };
export type { PromptsLayoutBuildDependencies };
