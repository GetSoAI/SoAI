/* SoAI - Shared storage defaults [frontend/assets/ts/core/storage/defaults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageCache } from '@core/storage/types.ts';
import { getDefaultChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { DEFAULT_INTERFACE_SCALE_PERCENT } from '@core/layout/interfaceScale.ts';

const createStorageDefaults = (): StorageCache => {
    const chatPreferenceParameters = getDefaultChatParameters();
    const hideRealModelDefault = chatPreferenceParameters.hideRealModel;

    return {
        ui: {
            theme: 'auto',
            accentColor: null,
            surfaceColor: null,
            promptEnhancerModel: null,
            dashboardLayout: null,
            interfaceScale: DEFAULT_INTERFACE_SCALE_PERCENT,
            language: 'en',
            clockFormat: '24h',
            headerClockEnabled: true,
            clockSecondsEnabled: false,
            regionalLocale: 'auto',
            dateFormat: 'auto',
            measurementUnits: 'auto',
            notificationDuration: 5,
            codeRecognitionEnabled: true,
            reduceMotions: false,
            soundEffects: true,
            liveStatusOverlayEnabled: false,
            modalStates: {},
            wallpaperOverlay: 0,
            solidBackground: null,
            glassEnabled: false,
            hiddenSidebarPages: ['settings', 'about', 'logs'],
            showMainStatusIndicator: true,
            mainStatePreferenceVersion: 1,
            hiddenDashboardElements: [],
            dashboardLocked: false,
            dashboardImageCard: null,
            dashboardImageCardFit: 'contain',
            dashboardMemo: null,
            chartColorMode: 'auto',
            chartStaticColor: '#4ade80',
            headerAutoHide: true,
            showScrollToTopButton: true,
            pageAnimation: 'slide',
            modalAnimation: 'scale',
            notificationAnimation: 'slide',
            animationSpeed: 'normal',
            lastVirtualModelStrategy: 'load_balancing'
        },
        chat: {
            preferences: {
                parameters: chatPreferenceParameters,
                hideRealModel: hideRealModelDefault,
                userSystemPromptLockEnabled: false,
                userSystemPromptLockValue: null
            },
            defaultEmbeddingModel: null,
            textZoom: 1,
            widescreenMode: false,
            sidebarOpen: true,
            showFavoritesAtTop: false,
            planBarVisible: true,
            assistantAvatar: null,
            userAvatar: null
        },
        logs: { lineLimit: 250, textZoom: 1 },
        terminal: { textZoom: 1 },
        search: { recent: [] },
        hardware: { refreshInterval: 1000, showGraphs: true, graphTimeRange: 60, gpuSettings: {} },
        filters: {
            pageControls: {
                models: { filterProvider: 'all', sortBy: 'none', sortOrder: 'asc' },
                plugins: { filterProvider: 'all', filterStatus: 'all', sortBy: 'none', sortOrder: 'asc' },
                prompts: { sortBy: 'none', sortOrder: 'asc' },
                fileExplorer: { sortBy: 'name', sortOrder: 'asc' },
                modelDetail: { parameterFilter: 'all' },
                logs: { source: 'core' },
                metrics: {
                    chartType: 'area',
                    category: 'metrics',
                    subcategory: 'requests',
                    timeRange: 120,
                    candleInterval: 1,
                    pluginHealthSort: { column: 'name', direction: 'asc' },
                    apiKeyUsageSort: { column: 'requests', direction: 'desc' },
                    modelTableSort: { column: 'requests', direction: 'desc' },
                    frontendTelemetrySort: { column: 'metric', direction: 'asc' },
                    systemStatsSort: { column: '', direction: 'asc' }
                },
                hardware: {
                    chartType: 'area',
                    category: 'cpu',
                    subcategory: 'usage',
                    timeRange: 120,
                    candleInterval: 1,
                    processSort: { column: 'cpu', direction: 'desc' }
                },
                osNetwork: { column: 'device', direction: 'asc' },
                osStorage: { column: 'mount', direction: 'asc' },
                updates: { column: 'name', direction: 'asc' }
            }
        },
        wizard: { completed: false },
        settings: { advancedMode: false },
        misc: {}
    };
};

export { createStorageDefaults };
