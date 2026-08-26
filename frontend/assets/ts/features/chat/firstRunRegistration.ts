/* SoAI - Chat feature first run registration [frontend/assets/ts/features/chat/firstRunRegistration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FirstRunModalRegistration } from '@core/firstrun/protocols.ts';
import { CHAT_MEMORY_PROFILE_MODAL_ID } from '@features/chat/modals/constants.ts';

const CHAT_MEMORY_PROFILE_FIRST_RUN_REGISTRATION: FirstRunModalRegistration = Object.freeze({
    id: 'chatMemoryProfile',
    pageId: 'chat',
    modalId: CHAT_MEMORY_PROFILE_MODAL_ID,
    allowManualOpen: true
});

export { CHAT_MEMORY_PROFILE_FIRST_RUN_REGISTRATION };
