/* SoAI - Chat feature message constants [frontend/assets/ts/features/chat/message/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const CHAT_MESSAGE_ROLE_CLASSES: ReadonlySet<string> = Object.freeze(new Set(['system', 'user', 'assistant', 'tool']));

const CHAT_MESSAGE_ROLE_ICONS: Readonly<Record<string, IconName>> = Object.freeze({
    system: 'info',
    user: 'user',
    assistant: 'model-default',
    tool: 'plugin'
});

export { CHAT_MESSAGE_ROLE_CLASSES, CHAT_MESSAGE_ROLE_ICONS };
