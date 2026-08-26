/* SoAI - Chat configuration controller contracts [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters, ConversationSettingsActionResult, Conversation } from '@features/chat/public.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

export interface TextZoomController {
    currentZoom: number;
    persistZoom(zoom: number): void;
}

export interface StorageManager {
    saveState?: (force?: boolean) => void;
    savePreferences?: () => void;
}

interface ParameterManager {
    updateParameterUI?: () => void;
    isParameterLocked(parameter: string): boolean;
}

export interface ConfigurationModelControlHost extends PageDomOwnerHost {
    pageContext: { sanitizer: SanitizerApi };
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    isSelectionLocked(): boolean;
    getCurrentConversation(): Conversation | null;
    isConversationExecuting(conversationId: string): boolean;
    navigateWithQuery(page: string, query: Record<string, string>): void;
}

export interface ConfigurationControllerHost extends PageDomOwnerHost, PageFeedbackOwnerHost {
    root: Element;
    modelControl: ConfigurationModelControlHost;

    applyTextZoom: () => void;
    applyWidescreenMode: () => void;
    applyInputActionVisibility: () => void;
    syncToolsEnabledToConversation: (enabled: boolean) => void;
    syncToolApprovalRequiredToConversation: (required: boolean) => void;
    persistParametersToConversation: () => void;
    prepareStagedConversationConfiguration: (configuration: { parameters: ChatParameters; model: string | null; comparisonModels: string[]; parametersDirty: boolean; modelDirty: boolean }) => () => Promise<Readonly<{ active: boolean; degraded: boolean }>>;
    prepareStagedConfigurationPreferences: (parameters: ChatParameters, model: string | null, isPresentationActive: () => boolean) => () => Promise<void>;
    persistBackendChatPreferences: () => Promise<void>;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    refreshConversationsUI: () => Promise<void>;
    refreshChatWorkerRendering: () => void;
}

export interface ConfigurationControllerStateAccess {
    getParameters: () => ChatParameters;
    setParameters: (parameters: ChatParameters) => void;
    getTextZoom: () => number;
    setTextZoom: (zoom: number) => void;
    getTextZoomController: () => TextZoomController | null;
    getStorageManager: () => StorageManager | null;
    getParameterManager: () => ParameterManager | null;
    isRichTextEnabled: () => boolean;
    hasWritableCurrentConversation: () => boolean;
    getCurrentModel: () => string | null;
    setCurrentModel: (model: string | null) => void;
    getModels: () => readonly ModelData[];
    getModelIndex: () => ReadonlyMap<string, ModelData>;
    hasModelCatalog: () => boolean;
}

export interface ConversationSettingsAction {
    hasChanges: boolean;
    isValid: boolean;
    handler: (() => Promise<ConversationSettingsActionResult>) | null;
    isStillValid: () => boolean;
}

export interface ConversationSettingsSavePlan {
    conversation: ConversationSettingsAction | null;
    knowledge: ConversationSettingsAction | null;
    tools: ConversationSettingsAction | null;
}
