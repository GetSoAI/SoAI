/* SoAI - Settings page system manager contracts [frontend/assets/ts/pages/settings/controllers/systemmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationDeleteAllResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import type { MessageResponse } from '@core/api/contracts/systemContracts.ts';
import type { FactoryResetResponse } from '@core/api/contracts/adminContracts.ts';
import type { ApplicationRestartResponse } from '@core/api/contracts/powerContracts.ts';
import type { PasswordVaultResetResponse } from '@core/api/contracts/webuiUserContracts.ts';
import type { WebuiChatPresetResetResponse } from '@core/api/contracts/webuiChatPresetContracts.ts';
import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost } from '@core/ui/controllerHosts.ts';

interface SystemManagerDependencies {
    host: SystemManagerHost;
}

type SystemManagerActionId = 'settings.system.resetAclPolicy' | 'settings.system.resetAppearance' | 'settings.system.resetMetrics' | 'settings.system.resetHardwareHistory' | 'settings.system.resetPageLayouts' | 'settings.system.resetPreferences' | 'settings.system.resetChatPresets' | 'settings.system.clearPromptHistory' | 'settings.system.resetRecentSearches' | 'settings.system.deleteAllConversations' | 'settings.system.resetToolApprovalPermissions' | 'settings.system.resetPasswordManager' | 'settings.system.resetConfiguration' | 'settings.system.factoryReset';

interface SystemActionConfig {
    id: string;
    actionId: SystemManagerActionId;
    title: string;
    description: string;
    enabled: boolean;
    unsupported?: string;
    buttonLabel?: string;
    className?: string;
}

interface SystemManagerApiHost {
    resetUiPreferencesRemote: () => Promise<MessageResponse>;
    resetUiPreferencesLocal: (options: { preserveWizardState: boolean }) => void;
    resetAppearancePreferences: () => Promise<void>;
    resetAclPolicy: () => Promise<void>;
    refreshAclPolicyAfterReset: () => Promise<void> | void;
    resetMetrics: () => Promise<MessageResponse>;
    resetHardwareHistory: () => Promise<MessageResponse>;
    resetMovablePageLayouts: () => void;
    resetChatPresets: () => Promise<WebuiChatPresetResetResponse>;
    resetRecentSearches: () => void;
    clearPromptHistory: () => Promise<void>;
    deleteAllConversations: () => Promise<ConversationDeleteAllResponse>;
    resetToolApprovalPermissions: () => Promise<MessageResponse>;
    resetPasswordVault: () => Promise<PasswordVaultResetResponse>;
    resetConfiguration: () => Promise<ApplicationRestartResponse>;
    factoryReset: () => Promise<FactoryResetResponse>;
    getWallpaperOverlay: () => number;
    getSolidBackground: () => string | null;
}

interface SystemManagerDomHost extends DomMutationHost, DomQueryHost, DomEventHost {
    setUIValue: (target: string | Element, value: string | null | undefined, options?: { attribute?: string }) => void;
}

interface SystemManagerExecutionHost extends ExecutionHost {
    withButtonDisabled: <T>(btn: Element, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
}

interface SystemManagerWorkflowHost {
    canRunSystemAction: (action: SystemManagerActionId) => boolean;
    setTimer: (functionValue: () => void, delay: number) => number;
    clearTimer: (timerId: number | null | undefined) => void;
    applyWallpaperOverlay: (value: string) => void;
    refreshWallpaperPreview: () => void;
    refreshSettingsAfterPreferencesReset: () => Promise<void> | void;
    navigate: (route: string, options?: Record<string, JsonValue>) => void;
    filterSettings: () => void;
    showRestartOverlay: (value: string) => void;
}

interface SystemManagerHost {
    api: SystemManagerApiHost;
    view: SystemManagerDomHost;
    execution: SystemManagerExecutionHost;
    notifications: NotificationHost;
    workflow: SystemManagerWorkflowHost;
}

interface ManagedTimerState {
    value: number | null;
}

interface ResetActionExecutionContext {
    host: SystemManagerHost;
    button: HTMLButtonElement;
}

interface FactoryResetExecutionContext extends ResetActionExecutionContext {
    timerState: ManagedTimerState;
}

export type { FactoryResetExecutionContext, ManagedTimerState, ResetActionExecutionContext, SystemActionConfig, SystemManagerActionId, SystemManagerApiHost, SystemManagerDependencies, SystemManagerDomHost, SystemManagerExecutionHost, SystemManagerHost };
