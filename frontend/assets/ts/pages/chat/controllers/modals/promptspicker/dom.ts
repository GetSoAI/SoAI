/* SoAI - Chat prompts picker modal required refs [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_PROMPTS_PICKER_MODAL_ID } from '@features/chat/public.ts';
import type { ChatPromptsPickerRefs } from '@pages/chat/controllers/modals/promptspicker/types.ts';

const resolveChatPromptsPickerRefs = (root: HTMLElement): ChatPromptsPickerRefs => {
    const searchInput = dom.resolve(modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'search'), root);
    const searchButton = dom.resolve(modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'search-button'), root);
    const results = dom.resolve(modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'results'), root);
    const status = dom.resolve(modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'status'), root);
    const manageButton = dom.resolve(modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'manage'), root);
    if (!(searchInput instanceof HTMLInputElement)) {
        throw new Error('Chat prompts picker requires a search input');
    }
    if (!(searchButton instanceof HTMLButtonElement)) {
        throw new Error('Chat prompts picker requires a search button');
    }
    if (!(results instanceof HTMLElement)) {
        throw new Error('Chat prompts picker requires a results container');
    }
    if (!(status instanceof HTMLElement)) {
        throw new Error('Chat prompts picker requires a status element');
    }
    if (!(manageButton instanceof HTMLButtonElement)) {
        throw new Error('Chat prompts picker requires a manage button');
    }
    return { root, searchInput, searchButton, results, status, manageButton };
};

export { resolveChatPromptsPickerRefs };
