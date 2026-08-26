/* SoAI - Chat feature conversation settings host [frontend/assets/ts/features/chat/conversationsettings/conversationSettingsHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import type { SetUIValueOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { ChatConversationMcpApi, ChatConversationRagApi, ChatConversationSearchApi, ChatPageApi, ModelStreamReadiness } from '@features/chat/pagecontracts/types.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { RagIngestionAttachmentSource, RagIngestionStatus } from '@features/chat/ingestion/types.ts';
import type { ConversationWorkspacePathConfig, McpConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { ChatConfigurationTabId } from '@features/chat/conversationsettings/chatConfigurationTabs.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';

type ConversationSettingsMcpApi = ChatConversationMcpApi;
type ConversationSettingsRagApi = ChatConversationRagApi;
type ConversationSettingsSearchApi = ChatConversationSearchApi;
type ConversationSettingsActionResult = void | Readonly<{ type: 'continue-degraded' }>;

interface ConversationSettingsActionInput {
    hasChanges: boolean;
    isValid?: boolean | undefined;
    handler: (() => Promise<ConversationSettingsActionResult>) | null;
    isStillValid?: (() => boolean) | undefined;
}

interface ConversationSettingsSavePlanInput {
    conversation?: ConversationSettingsActionInput | null | undefined;
    knowledge?: ConversationSettingsActionInput | null | undefined;
    tools?: ConversationSettingsActionInput | null | undefined;
}

interface ConversationSettingsChatApi {
    rag: ChatConversationRagApi;
    search: ChatConversationSearchApi;
    mcp: ChatConversationMcpApi;
}

interface ConversationSettingsDomService {
    getDocument(): Document;
    getData(element: Element | null, key: string): string | null;
    setStyle(element: HTMLElement, prop: string, value: string | null): void;
}

interface ConversationSettingsConversationManager {
    ensureConversationPersisted(conversation: Conversation): Promise<void>;
    updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
}

interface ConversationSettingsStorageManager {
    saveState(force?: boolean): void;
}

interface ConversationSettingsDomPort {
    on: (target: EventTarget, eventName: string, handler: EventListener) => () => void;

    createElement: (tag: string, options?: ElementOptions, content?: string | Node) => HTMLElement;
    appendToElement: (parent: Element, child: Node | Node[]) => void;
    setUIValue: (element: Element, value: DomPropertyValue, options?: SetUIValueOptions) => void;
    updateHTML: (element: Element, html: string) => void;
    updateText: (element: Element, text: string) => void;
    updateAttribute: (element: Element, attr: string, value: string | null) => void;
    updateProperty: (element: Element, prop: string, value: DomPropertyValue) => void;
    toggleClassName: (element: Element, className: string, add: boolean) => void;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
    dom: ConversationSettingsDomService;
}

interface ConversationSettingsDataPort {
    storage: ChatUiStorage;
    api: ChatPageApi;
    conversationManager: ConversationSettingsConversationManager;
    storageManager: ConversationSettingsStorageManager;
    getCurrentConversation: () => Conversation | null;
    getCurrentModel: () => string | null;
    isConversationExecuting: (conversationId: string) => boolean;
}

interface ConversationSettingsRagPort {
    getRagIngestionStatus: (conversationId: string) => RagIngestionStatus | null;
    subscribeRagIngestionStatus: (handler: () => void) => () => void;
    startRagIngestion: (inputArguments: { conversationId: string; conversation: Conversation; files: File[]; attachmentSource: RagIngestionAttachmentSource }) => Promise<void>;
    cancelRagIngestion: (conversationId: string) => Promise<void>;
}

interface ConversationSettingsWorkflowPort {
    isAdmin: () => boolean;
    applyMcpConfigToConversationModelSettings: (conversationId: string, config: McpConfig) => void;
    updateConversationWorkspacePathConfig: (conversationId: string, config: ConversationWorkspacePathConfig) => void;
    prepareMcpDefaultsProjection: () => (config: McpConfig) => Promise<boolean>;
    prepareRagDefaultsProjection: () => (response: RagConfigResponse) => Promise<boolean>;

    runWithBoundary: <T>(name: string, functionValue: () => Promise<T> | T) => Promise<T>;
    showNotification: (message: string, type: NotificationType, duration?: number) => void;
    setConversationSettingsSavePlan: (plan: ConversationSettingsSavePlanInput | null) => void;
    activateConversationSettingsTab: (tabId: ChatConfigurationTabId) => void;
    ensureModelStream: () => Promise<ModelStreamReadiness>;
    modelStreamHasPayload: boolean;
    models: readonly ModelData[] | null | undefined;

    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    refreshTokenCounterPreview: () => void;
}

interface ConversationSettingsHost {
    view: ConversationSettingsDomPort;
    data: ConversationSettingsDataPort;
    rag: ConversationSettingsRagPort;
    workflow: ConversationSettingsWorkflowPort;
}

const requireConversationSettingsChatApi = (host: ConversationSettingsHost): ConversationSettingsChatApi => {
    const chat = host.data.api.webui.chat;

    return {
        rag: chat.rag,
        search: chat.search,
        mcp: chat.mcp
    };
};

export type { ConversationSettingsHost, ConversationSettingsChatApi, ConversationSettingsMcpApi, ConversationSettingsRagApi, ConversationSettingsSearchApi, ConversationSettingsActionInput, ConversationSettingsActionResult, ConversationSettingsSavePlanInput };
export { requireConversationSettingsChatApi };
