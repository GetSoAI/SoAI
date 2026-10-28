/* SoAI - Chat feature memory profile modal [frontend/assets/ts/features/chat/modals/chatMemoryProfileModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { dom } from '@core/dom/dom.ts';
import { CHAT_MEMORY_PROFILE_VISIBLE_FIELD_NAMES, isChatMemoryProfileFieldName } from '@features/chat/modals/chatMemoryProfileFields.ts';
import { readFirstRunModalStateStatus, setFirstRunModalDismissed } from '@core/firstrun/state.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { wallClockMs } from '@core/time/clock.ts';
import { CHAT_MEMORY_PROFILE_MODAL_ID } from '@features/chat/modals/constants.ts';
import { bindChatMemoryProfileModal, CHAT_MEMORY_UPDATED_EVENT, type ChatMemoryProfileModalDependencies } from '@features/chat/modals/chatMemoryProfileModalBinding.ts';
import { createChatMemoryProfileModalElement } from '@features/chat/modals/markup/chatMemoryProfileModalMarkup.ts';

const createChatMemoryProfileModalDefinition = (dependencies: ChatMemoryProfileModalDependencies): ModalDefinition => {
    return {
        id: CHAT_MEMORY_PROFILE_MODAL_ID,
        layout: 'lg',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createChatMemoryProfileModalElement(),
        bind: (modal) => bindChatMemoryProfileModal(modal, dependencies),
        onOpen: (modal, options): void => {
            const manual = 'firstRunReason' in options && options.firstRunReason === 'manual';
            for (const field of dom.resolveAll('[data-profile-field]', modal)) {
                if (!(field instanceof HTMLElement)) continue;
                const name = field.dataset['profileField'];
                field.hidden = !manual && isChatMemoryProfileFieldName(name) && !CHAT_MEMORY_PROFILE_VISIBLE_FIELD_NAMES.includes(name);
            }
        },
        onClose: (modal, options): void => {
            if (options.reason === 'account-changed') return;
            if (modal.dataset['profileAccount'] !== String(getAuthManager().getCurrentUser()?.id)) return;
            if (options.reason === 'confirm') {
                return;
            }
            if (readFirstRunModalStateStatus(dependencies.storage, 'chatMemoryProfile') !== 'pending') {
                return;
            }
            setFirstRunModalDismissed(dependencies.storage, 'chatMemoryProfile', wallClockMs());
        }
    };
};

export { CHAT_MEMORY_UPDATED_EVENT, createChatMemoryProfileModalDefinition };
