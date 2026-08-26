/* SoAI - Chat page control layer DOM boundary contracts [frontend/assets/ts/pages/chat/controllers/page/dom/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatAttachmentManager, ChatParameters, Conversation } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatPageDomHost extends PageServicesOwnerHost, PageUiOwnerHost, PageDomOwnerHost {
    dom: {
        setStyle(element: HTMLElement, prop: string, value: string | null): void;
    };
}

interface ChatConversationDomHost extends ChatPageDomHost {
    conversationView: {
        current(): Conversation | null;
        isExecuting(conversationId: string): boolean;
    };
}

interface ChatPageColorPickerHost extends ChatPageDomHost, ChatConversationStateHost, ChatViewStateHost {
    isConversationExecuting(conversationId: string): boolean;
}

type ChatPageInputHintHost = ChatPageDomHost;

type ChatIconResolver = (name: IconName, options?: IconOptions) => TrustedHtml;

export type { ChatAttachmentManager, ChatConversationDomHost, ChatIconResolver, ChatPageColorPickerHost, ChatPageDomHost, ChatPageInputHintHost, ChatParameters };
