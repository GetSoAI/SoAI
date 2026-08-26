/* SoAI - Messaging settings feature types [frontend/assets/ts/features/settings/messaging/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccount, MessagingAccountCreate, MessagingAccountUpdate, MessagingPlatform } from '@core/api/contracts/messagingAccountContracts.ts';
import type { WebuiMessagingAccountEndpoints } from '@core/api/endpoints/webuiMessagingAccounts.ts';
import type { ReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import type { McpFormCatalog } from '@core/mcp/configTypes.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { WorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type MessagingModelCatalogStatus = 'idle' | 'ready' | 'error';

interface MessagingModelOption {
    readonly executionId: string;
    readonly detailUniversalId: string | null;
    readonly displayName: string;
    readonly contextWindowTokens: number | null;
    readonly openaiCapabilities: JsonObject | null;
    readonly supportedReasoningLevels: readonly ReasoningEffortLevel[] | null;
}

interface MessagingFieldDescriptor {
    key: string;
    uiToken: string;
    inputType: 'text' | 'password';
    minLength: number;
    maxLength: number;
    pattern: RegExp | null;
    defaultValue: string;
}

interface MessagingProviderDescriptor {
    id: MessagingPlatform;
    fields: readonly MessagingFieldDescriptor[];
}

type MessagingAccountModalResult = MessagingAccount;

interface MessagingAccountModalOptions {
    mode: 'create' | 'edit';
    account: MessagingAccount | null;
    models: readonly MessagingModelOption[];
    mcpCatalog: McpFormCatalog;
    workspaceBrowserAccess: WorkspaceBrowserAccess;
    persist(payload: MessagingAccountCreate | MessagingAccountUpdate): Promise<MessagingAccount>;
}

interface MessagingManagerHost extends PageDomOwnerHost, PageFeedbackOwnerHost {
    api: WebuiMessagingAccountEndpoints;
    resolveWorkspaceBrowserAccess(): Promise<WorkspaceBrowserAccess>;
    runWithBoundary<T>(name: string, task: () => Promise<T> | T): Promise<T>;
    confirmAndExecute<Result>(boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null): Promise<void>;
    hasSearchQuery(): boolean;
    filterSettings(): void;
}

interface MessagingManagerDependencies {
    host: MessagingManagerHost;
}

export type { MessagingAccountModalOptions, MessagingAccountModalResult, MessagingFieldDescriptor, MessagingManagerDependencies, MessagingManagerHost, MessagingModelCatalogStatus, MessagingModelOption, MessagingProviderDescriptor };
