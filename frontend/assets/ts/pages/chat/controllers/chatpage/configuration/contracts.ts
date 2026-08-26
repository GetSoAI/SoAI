/* SoAI - Chat configuration modal controller contracts [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatMemoryTabHost } from '@pages/chat/widgets/memorytab/service.ts';

interface ChatConfigurationDomainPort extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationViewHost, ChatComposerHost, ChatModelSessionHost, ChatPagePresentationHost {}

interface ChatConfigurationPlatformPort extends PageLayoutOwnerHost, PageServicesOwnerHost, PageDomOwnerHost, PageFeedbackOwnerHost {}

interface ChatConfigurationDependencies extends ChatConfigurationDomainPort, ChatConfigurationPlatformPort, ChatUiTaskScopeHost {
    pageLifecycle: Pick<PageLifecycle, 'run'>;
    runtimeServices: Pick<ChatRuntimeServices, 'firstRunModals'>;
    settings: { storage: Pick<ChatUiStorage, 'getAssistantAvatar' | 'setAssistantAvatar' | 'getUserAvatar' | 'setUserAvatar'> };
    api: ChatMemoryTabHost['api'] & { webui: { chat: Pick<ChatPageApi['webui']['chat'], 'presets'> } };
}

export type { ChatConfigurationDependencies };
