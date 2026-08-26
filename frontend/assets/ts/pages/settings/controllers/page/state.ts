/* SoAI - Settings page state [frontend/assets/ts/pages/settings/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConfigurationManager } from '@core/configurationManager.ts';
import type { McpConnection, McpInteractionEntry, McpPromptEntry, McpResourceEntry, McpRootEntry, McpSearchKeyEntry, McpServer, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import type { ApiKey, ApiKeyQuotaSummary, BackupEntry, BackupListLoadStatus, BackupOperationState, TabDefinition, WallpaperMetadata } from '@core/settings/contracts.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { createSettingsCapabilityAvailability, NORMAL_TAB_DEFINITIONS, type AdvancedSettingsRenderer, type AnalyzeStructure, type ApiKeysManager, type ExternalAccountsManager, type McpManager, type MessagingManager, type SecurityManager, type SettingsCapabilityAvailability } from '@features/settings/public.ts';
import type { AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import type { SecurityHardeningAudit, SystemHealthResponse } from '@core/api/contracts/systemContracts.ts';
import type { AclManager } from '@pages/settings/controllers/AclManager.ts';
import type { BackupManager } from '@pages/settings/controllers/backupmanager/BackupManager.ts';
import type { SettingsProductManager } from '@core/edition/settingsContribution.ts';
import type { PreferencesManager } from '@pages/settings/controllers/PreferencesManager.ts';
import type { SettingsSearchHost } from '@pages/settings/controllers/settingsSearchFiltering.ts';
import type { SystemManager } from '@pages/settings/controllers/systemmanager/SystemManager.ts';
import type { ThemeManager } from '@pages/settings/controllers/thememanager/ThemeManager.ts';
import type { UsersManager } from '@pages/settings/controllers/UsersManager.ts';
import type { InstanceIdentityManager } from '@pages/settings/controllers/instanceidentity/InstanceIdentityManager.ts';
import type { SettingsUi } from '@pages/settings/types.ts';
import type { LicensingManager } from '@pages/settings/controllers/LicensingManager.ts';

interface RestartOverlayService {
    show(value: string): void;
}

interface SettingsDirtyStateSurface {
    initialize(): void;
    syncConfigField(path: string, valid: boolean): void;
    syncUiPreferenceField(sourceKey: string): void;
    syncManualField(key: string, modified: boolean, valid: boolean): void;
    clearManualField(key: string): void;
    refreshRenderedFields(): void;
    clearAll(): void;
    hasInvalidFields(): boolean;
}

interface SettingsPageState {
    currentSection: string;
    advancedMode: boolean;
    advancedAccessEnabled: boolean;
    productSettingsEnabled: boolean;
    grantedActions: ReadonlySet<string>;
    coreConfig: JsonObject;
    users: WebuiUser[];
    usersAvailability: SettingsCapabilityAvailability;
    currentUserId: string | null;
    configManager: ConfigurationManager | null;
    uiPrefsManager: ConfigurationManager | null;
    dirtyStateManager: SettingsDirtyStateSurface | null;
    advancedTabs: TabDefinition[];
    advancedStructure: AnalyzeStructure | null;
    advancedRenderer: AdvancedSettingsRenderer | null;
    currentWallpaperUrl: string | null;
    currentWallpaperMetadata: WallpaperMetadata | null;
    currentSolidBackground: string | null;
    wallpaperRefreshPending: boolean;
    navigationGuardCleanup: (() => void) | null;
    uiCache: Map<string, Element>;
    restartOverlay: RestartOverlayService;
    ui: SettingsUi | null;
    aclPolicy: AclPolicyResponse | null;
    aclAvailability: SettingsCapabilityAvailability;
    securityAudit: SecurityHardeningAudit | null;
    securityAvailability: SettingsCapabilityAvailability;
    instanceIdentity: SystemHealthResponse | null;
    apiKeys: ApiKey[];
    apiKeyQuotaSummaries: Record<string, ApiKeyQuotaSummary>;
    showRevokedKeys: boolean;
    mcpStatus: McpStatus | null;
    mcpServers: McpServer[];
    mcpConnections: McpConnection[];
    mcpSearchKeys: McpSearchKeyEntry[];
    mcpSearchProviders: string[];
    mcpRoots: McpRootEntry[];
    mcpInteractions: McpInteractionEntry[];
    mcpTools: McpToolEntry[];
    mcpResources: McpResourceEntry[];
    mcpPrompts: McpPromptEntry[];
    mcpServerEditId: string | null;
    mcpServerEditBaseline: McpServer | null;
    mcpRootEditIndex: number | null;
    backups: BackupEntry[];
    backupListLoadStatus: BackupListLoadStatus;
    backupOperation: BackupOperationState | null;
    preferencesManager: PreferencesManager | null;
    instanceIdentityManager: InstanceIdentityManager | null;
    themeManager: ThemeManager | null;
    usersManager: UsersManager | null;
    aclManager: AclManager | null;
    apiKeysManager: ApiKeysManager | null;
    securityManager: SecurityManager | null;
    licensingManager: LicensingManager | null;
    mcpManager: McpManager | null;
    externalAccountsManager: ExternalAccountsManager | null;
    messagingManager: MessagingManager | null;
    backupManager: BackupManager | null;
    systemManager: SystemManager | null;
    productManagers: ReadonlyMap<string, SettingsProductManager>;
    settingsSearchHost: SettingsSearchHost | null;
    initialRouteParameters: JsonObject | null;
}

const createInitialSettingsPageState = (restartOverlay: RestartOverlayService): SettingsPageState => {
    const defaultTab = NORMAL_TAB_DEFINITIONS[0];
    return {
        currentSection: defaultTab ? defaultTab.id : 'general',
        advancedMode: false,
        advancedAccessEnabled: false,
        productSettingsEnabled: false,
        grantedActions: new Set(),
        coreConfig: {},
        users: [],
        usersAvailability: createSettingsCapabilityAvailability(),
        currentUserId: null,
        configManager: null,
        uiPrefsManager: null,
        dirtyStateManager: null,
        advancedTabs: [],
        advancedStructure: null,
        advancedRenderer: null,
        currentWallpaperUrl: null,
        currentWallpaperMetadata: null,
        currentSolidBackground: null,
        wallpaperRefreshPending: false,
        navigationGuardCleanup: null,
        uiCache: new Map<string, Element>(),
        restartOverlay,
        ui: null,
        aclPolicy: null,
        aclAvailability: createSettingsCapabilityAvailability(),
        securityAudit: null,
        securityAvailability: createSettingsCapabilityAvailability(),
        instanceIdentity: null,
        apiKeys: [],
        apiKeyQuotaSummaries: {},
        showRevokedKeys: false,
        mcpStatus: null,
        mcpServers: [],
        mcpConnections: [],
        mcpSearchKeys: [],
        mcpSearchProviders: [],
        mcpRoots: [],
        mcpInteractions: [],
        mcpTools: [],
        mcpResources: [],
        mcpPrompts: [],
        mcpServerEditId: null,
        mcpServerEditBaseline: null,
        mcpRootEditIndex: null,
        backups: [],
        backupListLoadStatus: 'idle',
        backupOperation: null,
        preferencesManager: null,
        instanceIdentityManager: null,
        themeManager: null,
        usersManager: null,
        aclManager: null,
        apiKeysManager: null,
        securityManager: null,
        licensingManager: null,
        mcpManager: null,
        externalAccountsManager: null,
        messagingManager: null,
        backupManager: null,
        systemManager: null,
        productManagers: new Map(),
        settingsSearchHost: null,
        initialRouteParameters: null
    };
};

export { createInitialSettingsPageState };
export type { RestartOverlayService, SettingsDirtyStateSurface, SettingsPageState };
