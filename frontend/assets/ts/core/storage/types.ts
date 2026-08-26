/* SoAI - Shared storage contracts [frontend/assets/ts/core/storage/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AnimationSpeed } from '@core/animations/speed.ts';
import type { InterfaceScalePercent } from '@core/layout/interfaceScale.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import type { JsonObject, JsonRecord } from '@core/types/jsonValues.ts';
import type { ChatUiParameters } from '@core/types/chatParameters.ts';

type AnimationType = 'fade' | 'slide' | 'scale' | 'zoom' | 'lateral';
type SyncGroup = 'ui' | 'chat' | 'logs' | 'terminal' | 'search' | 'hardware' | 'filters' | 'wizard' | 'settings';
type StorageType = 'localStorage' | 'sessionStorage';
type ThemeType = 'dark' | 'light' | 'auto';
type ClockFormatType = '24h' | '12h';
type ImageFitType = 'contain' | 'cover';
type ChartColorModeType = 'disabled' | 'static' | 'auto';
type SortOrderType = 'asc' | 'desc';
type PageControlPageId = 'models' | 'plugins' | 'prompts' | 'fileExplorer' | 'modelDetail' | 'logs' | 'metrics' | 'hardware' | 'osNetwork' | 'osStorage' | 'updates';

interface ChatPreferencesManager {
    parameters: ChatUiParameters;
    hideRealModel: boolean;
    userSystemPromptLockEnabled: boolean;
    userSystemPromptLockValue: string | null;
}

type ModalState = JsonObject;

interface UiPreferences {
    theme: ThemeType;
    accentColor: string | null;
    surfaceColor: string | null;
    promptEnhancerModel: string | null;
    dashboardLayout: JsonObject | null;
    interfaceScale: InterfaceScalePercent;
    language: string;
    clockFormat: ClockFormatType;
    headerClockEnabled: boolean;
    clockSecondsEnabled: boolean;
    regionalLocale: RegionalLocalePreference;
    dateFormat: DateFormatPreference;
    measurementUnits: MeasurementUnitsPreference;
    notificationDuration: number;
    codeRecognitionEnabled: boolean;
    reduceMotions: boolean;
    soundEffects: boolean;
    liveStatusOverlayEnabled: boolean;
    modalStates: Record<string, ModalState>;
    wallpaperOverlay: number;
    solidBackground: string | null;
    glassEnabled: boolean;
    hiddenSidebarPages: string[];
    showMainStatusIndicator: boolean;
    mainStatePreferenceVersion: number;
    hiddenDashboardElements: string[];
    dashboardLocked: boolean;
    dashboardImageCard: string | null;
    dashboardImageCardFit: ImageFitType;
    dashboardMemo: string | null;
    chartColorMode: ChartColorModeType;
    chartStaticColor: string;
    headerAutoHide: boolean;
    showScrollToTopButton: boolean;
    pageAnimation: AnimationType;
    modalAnimation: AnimationType;
    notificationAnimation: AnimationType;
    animationSpeed: AnimationSpeed;
    lastVirtualModelStrategy: VirtualModelStrategy;
}

type VirtualModelStrategy = 'load_balancing' | 'failover';

interface ChatCache {
    preferences: ChatPreferencesManager;
    defaultEmbeddingModel?: string | null;
    textZoom: number;
    widescreenMode: boolean;
    sidebarOpen: boolean;
    showFavoritesAtTop: boolean;
    planBarVisible: boolean;
    assistantAvatar: string | null;
    userAvatar: string | null;
}

interface LogsCache {
    lineLimit: number;
    textZoom: number;
}

interface TerminalCache {
    textZoom: number;
}

interface SearchCache {
    recent: string[];
}

interface HardwareCache {
    refreshInterval: number;
    showGraphs: boolean;
    graphTimeRange: number;
    gpuSettings: JsonRecord;
}

interface PageSortState {
    column: string;
    direction: SortOrderType;
}

interface ModelsPageControlState {
    filterProvider: string;
    sortOrder: SortOrderType;
    sortBy: string;
}

interface PluginsPageControlState {
    filterProvider: string;
    filterStatus: string;
    sortBy: string;
    sortOrder: SortOrderType;
}

interface PromptsPageControlState {
    sortBy: string;
    sortOrder: SortOrderType;
}

interface FileExplorerPageControlState {
    sortBy: string;
    sortOrder: SortOrderType;
}

interface ModelDetailPageControlState {
    parameterFilter: string;
}

interface LogsPageControlState {
    source: string;
}

interface ChartPageControlState {
    chartType: string;
    category: string;
    subcategory: string;
    timeRange: number;
    candleInterval: number;
}

interface MetricsPageControlState extends ChartPageControlState {
    pluginHealthSort: PageSortState;
    apiKeyUsageSort: PageSortState;
    modelTableSort: PageSortState;
    frontendTelemetrySort: PageSortState;
    systemStatsSort: PageSortState;
}

interface HardwarePageControlState extends ChartPageControlState {
    processSort: PageSortState;
}

interface PageControlStates {
    models: ModelsPageControlState;
    plugins: PluginsPageControlState;
    prompts: PromptsPageControlState;
    fileExplorer: FileExplorerPageControlState;
    modelDetail: ModelDetailPageControlState;
    logs: LogsPageControlState;
    metrics: MetricsPageControlState;
    hardware: HardwarePageControlState;
    osNetwork: PageSortState;
    osStorage: PageSortState;
    updates: PageSortState;
}

type PageControlState = ModelsPageControlState | PluginsPageControlState | PromptsPageControlState | FileExplorerPageControlState | ModelDetailPageControlState | LogsPageControlState | MetricsPageControlState | HardwarePageControlState | PageSortState;

interface FiltersCache {
    pageControls: PageControlStates;
}

interface WizardCache {
    completed: boolean;
}

interface SettingsCache {
    advancedMode: boolean;
}

interface StorageCache {
    ui: UiPreferences;
    chat: ChatCache;
    logs: LogsCache;
    terminal: TerminalCache;
    search: SearchCache;
    hardware: HardwareCache;
    filters: FiltersCache;
    wizard: WizardCache;
    settings: SettingsCache;
    misc: JsonRecord;
}

type SessionData = JsonObject;

interface StorageManagerState {
    ready: boolean;
    preferSession: boolean;
}

interface StorageCacheSnapshot {
    cache: StorageCache;
    version: number;
}

interface ThemeSurfaceConfig {
    id: string;
    className: string;
    theme: ThemeType;
    style?: string;
}

interface NotificationSettings {
    duration: number;
    animation: AnimationType;
}

interface ThemeState {
    theme: ThemeType;
    time: number;
}

interface ThemeModeState {
    theme: ThemeType;
    next: ThemeType;
    interval: number;
}

interface StorageManagerOptions {
    useSession?: boolean;
    cache?: StorageCache;
    defaults?: StorageCache;
}

export type { AnimationSpeed, AnimationType, ChartColorModeType, ChartPageControlState, ChatCache, ChatPreferencesManager, ClockFormatType, FileExplorerPageControlState, FiltersCache, HardwareCache, HardwarePageControlState, ImageFitType, LogsCache, LogsPageControlState, MetricsPageControlState, ModalState, ModelDetailPageControlState, ModelsPageControlState, NotificationSettings, PageControlPageId, PageControlState, PageControlStates, PageSortState, PluginsPageControlState, PromptsPageControlState, SearchCache, SessionData, SettingsCache, StorageCache, StorageCacheSnapshot, StorageManagerOptions, StorageManagerState, StorageType, SyncGroup, SortOrderType, TerminalCache, ThemeModeState, ThemeState, ThemeSurfaceConfig, ThemeType, UiPreferences, VirtualModelStrategy, WizardCache };
