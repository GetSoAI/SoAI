/* SoAI - Chat page presentation contracts [frontend/assets/ts/pages/chat/controllers/chatpage/presentation/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

interface ChatPagePresentationContract {
    assistantAvatarUrl(): string | null;
    userAvatarUrl(): string | null;
    cachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    updateExportButtonVisibility(): void;
    insertIcons(): void;
    showConversationColorPicker(conversationItem: HTMLElement, conversationId: string): void;
    hideConversationColorPicker(): void;
    conversationColorLabel(color: string | null): string | null;
}

interface ChatPagePresentationHost {
    presentation: ChatPagePresentationContract;
}

export type { ChatPagePresentationContract, ChatPagePresentationHost };
