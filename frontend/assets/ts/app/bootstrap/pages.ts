/* SoAI - Application page registration and dependency wiring [frontend/assets/ts/app/bootstrap/pages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPageRegistry, type PageOptions, type PageRegistry } from '@core/pageRegistry.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import { securityApi } from '@core/security/public.ts';
import { getLicenseService } from '@core/licenseservice/service.ts';
import type { createStorageService } from '@core/storage/StorageService.ts';
import { isFunction } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ChatPagePresenceService } from '@features/chat/background/ChatPagePresenceService.ts';
import type { ChatConversationAttentionService } from '@features/chat/background/ChatConversationAttentionService.ts';
import type { ChatStreamService } from '@features/chat/chatstreamservice/service.ts';
import type { ChatToolIconService } from '@features/chat/ChatToolIconService.ts';
import type { CatalogStore } from '@features/catalog/catalogSubscriptionManager.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationRunActivityServiceContract } from '@features/automation/runactivity/types.ts';
import type { HardwarePageStorage } from '@features/hardware/public.ts';
import type { LogStream } from '@features/logging/logstreamservice/service.ts';
import type { CountdownOverlay } from '@features/overlays/Countdown.ts';
import type { OperationType, RestartOverlayShowOptions } from '@features/overlays/public.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import type { SearchComponent } from '@features/search/SearchPanel.ts';
import { voiceCallRuntimeAssets } from '@app/entrypoints/voicecall/runtimeAssets.ts';
import { AboutPage } from '@pages/about/AboutPage.ts';
import { AutomationPage } from '@pages/automation/AutomationPage.ts';
import { ChatPage } from '@pages/chat/ChatPage.ts';
import { DashboardPage } from '@pages/dashboard/DashboardPage.ts';
import { ForbiddenPage } from '@pages/forbidden/ForbiddenPage.ts';
import { FileExplorerPage } from '@pages/fileexplorer/FileExplorerPage.ts';
import { HardwarePage } from '@pages/hardware/index.ts';
import { HelpPage } from '@pages/help/HelpPage.ts';
import { LoginPage } from '@pages/login/LoginPage.ts';
import { LogsPage } from '@pages/logs/LogsPage.ts';
import { MetricsPage } from '@pages/metrics/index.ts';
import { ModelDetailPage } from '@pages/modeldetail/ModelDetailPage.ts';
import { ModelsPage } from '@pages/models/ModelsPage.ts';
import { PluginsPage } from '@pages/plugins/PluginsPage.ts';
import type { PluginsFiltersStorage } from '@features/plugins/public.ts';
import { PowerPage } from '@pages/power/PowerPage.ts';
import { PromptsPage } from '@pages/prompts/PromptsPage.ts';
import { SearchPage } from '@pages/search/SearchPage.ts';
import { SettingsPage } from '@pages/settings/SettingsPage.ts';
import { TerminalPage } from '@pages/terminal/TerminalPage.ts';
import { UpdatesPage } from '@pages/updates/UpdatesPage.ts';
import { WizardPage } from '@pages/wizard/WizardPage.ts';

type SharedStorage = ReturnType<typeof createStorageService>;
type RegisteredPageClass = Parameters<PageRegistry['register']>[1];

const registerPage = (pageId: string, pageClass: RegisteredPageClass, options: Partial<PageOptions> = {}): void => {
    const pageRegistry = getPageRegistry();
    if (pageRegistry.has(pageId)) {
        throw new Error(`Page "${pageId}" is already registered`);
    }
    pageRegistry.register(pageId, pageClass, options);
};

const isSharedStorage = (value: SharedStorage): value is SharedStorage & PluginsFiltersStorage => {
    return isFunction(value.get) && isFunction(value.set) && isFunction(value.getPageControlState) && isFunction(value.getPageControlStates) && isFunction(value.setPageControlState) && isFunction(value.setPageControlStates);
};

const ensureSharedStorage = (value: SharedStorage): SharedStorage & PluginsFiltersStorage => {
    if (!isSharedStorage(value)) {
        throw new TypeError('registerPages storage must expose get/set and page control methods');
    }
    return value;
};

const createHardwareStorageAdapter = (storage: SharedStorage): HardwarePageStorage => ({
    get: (key: string, defaultValue: JsonObject): JsonObject => {
        const value = storage.get(key, defaultValue);
        if (!isJsonObject(value)) {
            throw new Error(`Hardware page storage value for "${key}" must be an object`);
        }
        return value;
    },
    set: (key: string, value: JsonObject): void => {
        storage.set(key, value);
    }
});

interface PageRegistrationDependencies {
    basePageDependencies: BasePageDependencies;
    chatStreamService: ChatStreamService;
    chatPagePresence: ChatPagePresenceService;
    chatConversationAttention: ChatConversationAttentionService;
    chatToolIconService: ChatToolIconService;
    firstRunModals: FirstRunModalService;
    automationRunActivity: AutomationRunActivityServiceContract;
    logStream: LogStream;
    countdownOverlay: CountdownOverlay;
    restartOverlay: { show(value: OperationType, options?: RestartOverlayShowOptions): void; hide(): void };
    powerOverlay: { show(value: string): void; hide(): void };
    searchComponent: SearchComponent;
    catalogStore: CatalogStore;
    storage: SharedStorage;
    automationDataService: AutomationDataService;
}

const registerPages = ({ basePageDependencies, chatStreamService, chatPagePresence, chatConversationAttention, chatToolIconService, firstRunModals, automationRunActivity, logStream, countdownOverlay, restartOverlay, powerOverlay, searchComponent, catalogStore, storage, automationDataService }: PageRegistrationDependencies): void => {
    const sharedStorage = ensureSharedStorage(storage);

    registerPage('about', AboutPage, { factory: () => new AboutPage(basePageDependencies) });
    registerPage('automation', AutomationPage, {
        factory: () =>
            new AutomationPage(
                {
                    dataService: automationDataService,
                    runActivity: automationRunActivity
                },
                basePageDependencies
            )
    });
    registerPage('chat', ChatPage, {
        factory: () => new ChatPage({ chatStreamService, chatPagePresence, chatConversationAttention, chatToolIconService, firstRunModals, voiceCallRuntimeAssets }, basePageDependencies)
    });
    registerPage('dashboard', DashboardPage, {
        factory: () => new DashboardPage({ firstRunModals, logStream, edition: requireFrontendEditionComposition().dashboard }, basePageDependencies)
    });
    registerPage('forbidden', ForbiddenPage, { factory: () => new ForbiddenPage(basePageDependencies) });
    registerPage('fileExplorer', FileExplorerPage, { factory: () => new FileExplorerPage(basePageDependencies) });
    registerPage('hardware', HardwarePage, {
        factory: () => {
            const hardwarePageDependencies = {
                storage: createHardwareStorageAdapter(sharedStorage),
                security: securityApi
            };
            return new HardwarePage(hardwarePageDependencies, basePageDependencies);
        }
    });
    registerPage('help', HelpPage, { factory: () => new HelpPage(basePageDependencies) });
    registerPage('login', LoginPage, { factory: () => new LoginPage(basePageDependencies) });
    registerPage('logs', LogsPage, { factory: () => new LogsPage(logStream, basePageDependencies) });
    registerPage('metrics', MetricsPage, { factory: () => new MetricsPage(basePageDependencies) });
    registerPage('modelDetail', ModelDetailPage, { factory: () => new ModelDetailPage(basePageDependencies) });
    registerPage('models', ModelsPage, {
        factory: () => new ModelsPage({ catalogStore }, basePageDependencies)
    });
    registerPage('plugins', PluginsPage, {
        factory: () =>
            new PluginsPage(
                {
                    storage: sharedStorage,
                    restartOverlay,
                    catalogStore,
                    firstRunModals
                },
                basePageDependencies
            )
    });
    registerPage('power', PowerPage, {
        factory: () => new PowerPage({ countdownOverlay, restartOverlay, powerOverlay }, basePageDependencies)
    });
    registerPage('prompts', PromptsPage, { factory: () => new PromptsPage(basePageDependencies) });
    registerPage('search', SearchPage, { factory: () => new SearchPage({ searchComponent }, basePageDependencies) });
    registerPage('settings', SettingsPage, {
        factory: () =>
            new SettingsPage(
                {
                    restartOverlay,
                    product: requireFrontendEditionComposition().settings,
                    dashboardTitle: requireFrontendEditionComposition().dashboard?.getTitle ?? null
                },
                basePageDependencies
            )
    });
    registerPage('terminal', TerminalPage, { factory: () => new TerminalPage(basePageDependencies) });
    registerPage('updates', UpdatesPage, {
        factory: () => new UpdatesPage({ restartOverlay, product: requireFrontendEditionComposition().updates }, basePageDependencies)
    });
    registerPage('wizard', WizardPage, {
        factory: () =>
            new WizardPage(
                {
                    licenseService: getLicenseService()
                },
                basePageDependencies
            )
    });
    for (const contribution of requireFrontendEditionComposition().pages) {
        registerPage(contribution.id, contribution.pageClass, contribution.options(basePageDependencies));
    }
};

export { registerPages };
