/* SoAI - Settings feature boundary contracts [frontend/assets/ts/features/settings/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AnimationSpeed, ClockFormatType } from '@core/storage/types.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import type { ApiKey, ApiKeyQuotaSummary } from '@core/settings/contracts.ts';
import type { MessageResponse } from '@core/api/contracts/systemContracts.ts';
import type { AcceptedPowerActionResponse, ApplicationRestartResponse } from '@core/api/contracts/powerContracts.ts';
import type { ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';
import type { McpAccessTokenCreateRequest, McpAccessTokenCreateResponse, McpAccessTokenRevokeResponse, McpAccessTokensListResponse } from '@core/api/contracts/mcpAccessTokenContracts.ts';
import type { WallpaperDownloadResponse, WallpaperUploadResponse } from '@core/api/contracts/wallpaperContracts.ts';
import type { AclPolicyOverrides, AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import type { ApiKeyCreateRequest, ApiKeyDeleteAllResponse, ApiKeyRevokeResponse, ApiKeySecretResponse } from '@core/api/contracts/apiKeyContracts.ts';
import type { ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import type { BackupListResponse, BackupTaskAcceptedResponse, FactoryResetResponse } from '@core/api/contracts/adminContracts.ts';
import type { PasswordVaultResetResponse, WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import type { IdentityMutationSuccess } from '@core/api/contracts/webuiIdentityMutationContracts.ts';
import type { SelfMutationRecoveryRequest } from '@core/auth/rotationRecovery.ts';
import type { McpConnection, McpInteractionEntry, McpInteractionResolvePayload, McpOauthStartResponse, McpOauthStatusResponse, McpPromptEntry, McpResourceEntry, McpRootEntry, McpRootsResponse, McpSearchKeyEntry, McpSearchKeysResponse, McpServer, McpServerConnectionResponse, McpServerCreatePayload, McpServerCreateResponse, McpServerUpdatePayload, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import type { HostFilesystemBrowserApi, ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationDeleteAllResponse, WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import type { ConversationSearchConfigResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { InterfaceScalePercent } from '@core/layout/interfaceScale.ts';

interface AuthService {
    isAuthenticated: boolean;
    getCurrentUser: () => WebuiUser | null;
    isAdmin: () => boolean;
    logout: () => void;
    runOwnIdentityMutation: (request: Omit<SelfMutationRecoveryRequest, 'signal'>) => Promise<IdentityMutationSuccess>;
}

interface StorageService {
    ready: Promise<void>;
    get: (key: string, defaultValue?: JsonValue | null | undefined) => JsonValue | null | undefined;
    set: (key: string, value: JsonValue | null | undefined) => void;
    remove: (key: string) => void;
    getLiveStatusOverlayEnabled: () => boolean;
    setLiveStatusOverlayEnabled: (enabled: boolean) => void;
    getNotificationDuration: () => number;
    setNotificationDuration: (duration: number) => void;
    setSolidBackground: (color: string | null) => void;
    getClockFormat: () => ClockFormatType;
    setClockFormat: (format: ClockFormatType) => void;
    getRegionalLocale: () => RegionalLocalePreference;
    setRegionalLocale: (locale: RegionalLocalePreference) => void;
    getDateFormat: () => DateFormatPreference;
    setDateFormat: (format: DateFormatPreference) => void;
    getMeasurementUnits: () => MeasurementUnitsPreference;
    setMeasurementUnits: (units: MeasurementUnitsPreference) => void;
    getTheme: () => string;
    setTheme: (theme: string) => string;
    getReduceMotions: () => boolean;
    setReduceMotions: (enabled: boolean) => void;
    getAccentColor: () => string | null;
    setAccentColor: (color: string | null) => void;
    getSurfaceColor: () => string | null;
    setSurfaceColor: (color: string | null) => void;
    getGlassEnabled: () => boolean;
    setGlassEnabled: (enabled: boolean) => void;
    getPageAnimation: () => string;
    setPageAnimation: (animation: string) => void;
    getModalAnimation: () => string;
    setModalAnimation: (animation: string) => void;
    getNotificationAnimation: () => string;
    setNotificationAnimation: (animation: string) => void;
    getAnimationSpeed: () => AnimationSpeed;
    setAnimationSpeed: (speed: AnimationSpeed) => void;
    getInterfaceScale: () => InterfaceScalePercent;
    setInterfaceScale: (percent: InterfaceScalePercent) => void;
    getWallpaperOverlay: () => number;
    setWallpaperOverlay: (value: number) => void;
    getSolidBackground: () => string | null;
    getHiddenSidebarPages: () => string[];
    setHiddenSidebarPages: (pages: string[]) => void;
    getHiddenDashboardElements: () => string[];
    setHiddenDashboardElements: (elements: string[]) => void;
    getSoundEffects: () => boolean;
    setSoundEffects: (enabled: boolean) => void;
    getHeaderAutoHide: () => boolean;
    setHeaderAutoHide: (enabled: boolean) => void;
    getShowMainStatusIndicator: () => boolean;
    setShowMainStatusIndicator: (enabled: boolean) => void;
    getDashboardLocked: () => boolean;
    setDashboardLocked: (locked: boolean) => void;
    getChartColorMode: () => string;
    setChartColorMode: (mode: string) => void;
    getChartStaticColor: () => string;
    setChartStaticColor: (color: string) => void;
    getAdvancedMode: () => boolean;
    setAdvancedMode: (value: boolean) => void;
    cache?: {
        wizard?: {
            completed?: boolean;
        };
    };
    clearSession?: () => void;
    setAuthenticated?: (authenticated: boolean) => Promise<void>;
}

interface ApiKeyCreateResponse {
    key: string;
    keyId: string;
    label?: string;
    prefix?: string;
}

interface ApiKeyRotateResponse {
    key: string;
    keyId: string;
}

interface ApiKeyListResponse {
    keys: ApiKey[];
}

interface SettingsPageApi {
    fileExplorer: ReadOnlyFileBrowserApi;
    webui: {
        acl: {
            updatePolicy: (overrides: AclPolicyOverrides) => Promise<AclPolicyResponse>;
            getPolicy: () => Promise<AclPolicyResponse>;
            resetPolicy: () => Promise<void>;
        };
        apiKeys: {
            create: (options: ApiKeyCreateRequest) => Promise<ApiKeySecretResponse>;
            revoke: (id: string) => Promise<ApiKeyRevokeResponse>;
            rotate: (id: string) => Promise<ApiKeySecretResponse>;
            delete: (id: string) => Promise<void>;
            deleteAll: () => Promise<ApiKeyDeleteAllResponse>;
            list: (showRevoked: boolean) => Promise<ApiKey[]>;
            getQuota: (id: string) => Promise<ApiKeyQuotaSummary>;
            updateQuota: (id: string, payload: ApiKeyQuotaUpdateRequest) => Promise<ApiKeyQuotaSummary>;
            listQuotaStatus: () => Promise<Record<string, ApiKeyQuotaSummary>>;
        };
        mcpAccessTokens: {
            list: () => Promise<McpAccessTokensListResponse>;
            create: (payload: McpAccessTokenCreateRequest) => Promise<McpAccessTokenCreateResponse>;
            revoke: (tokenId: string) => Promise<McpAccessTokenRevokeResponse>;
        };
        users: {
            list: (options?: { signal?: AbortSignal }) => Promise<WebuiUser[]>;
            create: (username: string, password: string, isAdmin: boolean) => Promise<WebuiUser>;
            update: (userId: number, isAdmin: boolean) => Promise<WebuiUser>;
            workspaceBrowser: HostFilesystemBrowserApi;
            updateWorkspacePath: (userId: number, workspacePath: string | null) => Promise<WebuiUser>;
            delete: (userId: number) => Promise<void>;
        };
        wallpaper: {
            upload: (file: File) => Promise<WallpaperUploadResponse>;
            download: (url: string) => Promise<WallpaperDownloadResponse>;
            delete: () => Promise<void>;
        };
        preferences: {
            resetUiPreferences: () => Promise<MessageResponse>;
            resetToolApprovalPermissions: () => Promise<MessageResponse>;
        };
        passwordVault: {
            reset: () => Promise<PasswordVaultResetResponse>;
        };
        chat: {
            list: () => Promise<WebuiConversationResponse[]>;
            deleteAll: () => Promise<ConversationDeleteAllResponse>;
            search: {
                getConfig: (id: string) => Promise<ConversationSearchConfigResponse>;
            };
        };
        admin: {
            resetConfiguration: () => Promise<ApplicationRestartResponse>;
            factoryReset: (options?: JsonObject) => Promise<FactoryResetResponse>;
            backups: {
                list: () => Promise<BackupListResponse>;
                create: () => Promise<BackupTaskAcceptedResponse>;
                restore: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
                verify: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
                remove: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
                export: (backupId: string) => Promise<Response>;
                exportUrl: (backupId: string) => string;
            };
        };
    };
    configs: {
        get: (key: string) => Promise<JsonObject>;
        update: (key: string, data: JsonValue) => Promise<ConfigUpdateResponse>;
    };
    mcp: {
        status: () => Promise<McpStatus>;
        servers: {
            list: () => Promise<McpServer[]>;
            create: (payload: McpServerCreatePayload) => Promise<McpServerCreateResponse>;
            update: (id: string, payload: McpServerUpdatePayload) => Promise<McpServer>;
            delete: (id: string) => Promise<void>;
            connect: (id: string) => Promise<McpServerConnectionResponse>;
            disconnect: (id: string) => Promise<McpServerConnectionResponse>;
        };
        oauth: {
            start: (id: string) => Promise<McpOauthStartResponse>;
            clear: (id: string) => Promise<{ status: 'cleared' }>;
            status: (id: string) => Promise<McpOauthStatusResponse>;
        };
        connections: {
            list: () => Promise<McpConnection[]>;
        };
        tools: {
            list: () => Promise<McpToolEntry[]>;
        };
        resources: {
            list: () => Promise<McpResourceEntry[]>;
        };
        prompts: {
            list: () => Promise<McpPromptEntry[]>;
        };
        roots: {
            get: () => Promise<McpRootsResponse>;
            update: (payload: { roots: McpRootEntry[] }) => Promise<McpRootsResponse>;
        };
        interactions: {
            list: () => Promise<McpInteractionEntry[]>;
            resolve: (id: string, payload: McpInteractionResolvePayload) => Promise<JsonObject>;
        };
        searchApiKeys: {
            list: () => Promise<McpSearchKeysResponse>;
            set: (provider: string, payload: { apiKey: string }) => Promise<McpSearchKeyEntry>;
            delete: (provider: string) => Promise<void>;
        };
    };
    system: {
        power: {
            restartApplication: () => Promise<AcceptedPowerActionResponse>;
        };
        resetMetrics: () => Promise<MessageResponse>;
        resetHardwareHistory: () => Promise<MessageResponse>;
    };
}

interface PageRouter {
    navigate(route: string, options?: { force?: boolean; replace?: boolean }): void;
}

interface PageSanitizer {
    html(input: string): string;
    attribute(input: string): string;
}

interface PageContext {
    sanitizer: PageSanitizer;
}

interface AdvancedRenderer {
    renderSectionContent(sectionKey: string, config: JsonObject): DocumentFragment | null;
}

export type { AuthService, StorageService, ApiKeyCreateResponse, ApiKeyRotateResponse, ApiKeyListResponse, MessageResponse, SettingsPageApi, PageRouter, PageSanitizer, PageContext, AdvancedRenderer };
