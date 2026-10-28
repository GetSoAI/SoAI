/* SoAI - Prompts picker modal required refs [frontend/assets/ts/features/prompts/picker/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { PROMPTS_PICKER_MODAL_ID } from '@features/prompts/modals/constants.ts';
import type { PromptsPickerRefs } from '@features/prompts/picker/types.ts';

const resolvePromptsPickerRefs = (root: HTMLElement): PromptsPickerRefs => {
    const searchInput = dom.resolve(modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'search'), root);
    const searchButton = dom.resolve(modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'search-button'), root);
    const results = dom.resolve(modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'results'), root);
    const status = dom.resolve(modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'status'), root);
    const manageButton = dom.resolve(modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'manage'), root);
    if (!(searchInput instanceof HTMLInputElement)) {
        throw new Error('Prompts picker requires a search input');
    }
    if (!(searchButton instanceof HTMLButtonElement)) {
        throw new Error('Prompts picker requires a search button');
    }
    if (!(results instanceof HTMLElement)) {
        throw new Error('Prompts picker requires a results container');
    }
    if (!(status instanceof HTMLElement)) {
        throw new Error('Prompts picker requires a status element');
    }
    if (!(manageButton instanceof HTMLButtonElement)) {
        throw new Error('Prompts picker requires a manage button');
    }
    return { root, searchInput, searchButton, results, status, manageButton };
};

export { resolvePromptsPickerRefs };
