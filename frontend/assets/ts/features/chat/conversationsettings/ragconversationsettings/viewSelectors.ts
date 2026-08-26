/* SoAI - Chat feature view selectors [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/viewSelectors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRagConversationElement, requireRagConversationInput, requireRagConversationSelect } from '@features/chat/conversationsettings/ragconversationsettings/dom.ts';
import type { RagViewSelectors } from '@features/chat/conversationsettings/ragconversationsettings/view.ts';

const createRagViewSelectors = (modal: Element | null): RagViewSelectors => {
    return {
        requireElement: (selector: string): Element => requireRagConversationElement(modal, selector),
        requireInput: (selector: string): HTMLInputElement => requireRagConversationInput(modal, selector),
        requireSelect: (selector: string): HTMLSelectElement => requireRagConversationSelect(modal, selector)
    };
};

export { createRagViewSelectors };
