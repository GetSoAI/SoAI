/* SoAI - Application page registration and dependency wiring [frontend/assets/ts/app/bootstrap/pages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPageRegistry, type PageOptions, type PageRegistry } from '@core/pageRegistry.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import { securityApi } from '@core/security/public.ts';
import { getLicenseService } from '@core/licenseservice/service.ts';
import type { createStorageService } from '@core/storage/StorageService.ts';
import { isFunction } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ChatPagePresenceServiceContract } from '@core/chat/protocols.ts';
import type { ChatConversationAttentionService } from '@features/chat/background/ChatConversationAttentionService.ts';
import type { ChatStreamService } from '@features/chat/chatstreamservice/service.ts';
import type { ChatToolIconService } from '@features/chat/ChatToolIconService.ts';
import type { CatalogStore } from '@features/catalog/catalogSubscriptionManager.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationRunActivityServiceContract } from '@features/automation/runactivity/types.ts';
import type { HardwarePageStorage } from '@features/hardware/public.ts';
import type { LogStream } from '@features/logging/logstreamservice/service.ts';
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
import { PromptsPage } from '@pages/prompts/PromptsPage.ts';
import { SearchPage } from '@pages/search/SearchPage.ts';
import type { ModelCatalogSubscriber } from '@core/models/modelCatalogObservation.ts';
import { SettingsPage } from '@pages/settings/SettingsPage.ts';
import { TerminalPage } from '@pages/terminal/TerminalPage.ts';
import { UpdatesPage } from '@pages/updates/UpdatesPage.ts';
import { WizardPage } from '@pages/wizard/WizardPage.ts';
import type { PageMountScope } from '@core/routing/router/types.ts';

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
    basePageDependencies: Omit<BasePageDependencies, 'router' | 'mountScope'>;
    chatStreamService: ChatStreamService;
    chatPagePresence: ChatPagePresenceServiceContract;
    chatConversationAttention: ChatConversationAttentionService;
    chatToolIconService: ChatToolIconService;
    firstRunModals: FirstRunModalService;
    automationRunActivity: AutomationRunActivityServiceContract;
    logStream: LogStream;
    restartOverlay: { show(value: OperationType, options?: RestartOverlayShowOptions): void; hide(): void };
    searchComponent: SearchComponent;
    catalogStore: CatalogStore;
    storage: SharedStorage;
    modelCatalogSubscriber: ModelCatalogSubscriber;
    automationDataService: AutomationDataService;
}

const registerPages = ({ basePageDependencies, chatStreamService, chatPagePresence, chatConversationAttention, chatToolIconService, firstRunModals, automationRunActivity, logStream, restartOverlay, searchComponent, catalogStore, storage, modelCatalogSubscriber, automationDataService }: PageRegistrationDependencies): void => {
    const sharedStorage = ensureSharedStorage(storage);
    const dependenciesForMount = (mountScope: PageMountScope): BasePageDependencies => Object.freeze({ ...basePageDependencies, router: mountScope.routing, mountScope });

    registerPage('about', AboutPage, { factory: (mountScope) => new AboutPage(dependenciesForMount(mountScope)) });
    registerPage('automation', AutomationPage, {
        factory: (mountScope) =>
            new AutomationPage(
                {
                    dataService: automationDataService,
                    runActivity: automationRunActivity
                },
                dependenciesForMount(mountScope)
            )
    });
    registerPage('chat', ChatPage, {
        factory: (mountScope) => new ChatPage({ chatStreamService, chatPagePresence, chatConversationAttention, chatToolIconService, firstRunModals, voiceCallRuntimeAssets }, dependenciesForMount(mountScope))
    });
    registerPage('dashboard', DashboardPage, {
        factory: (mountScope) => new DashboardPage({ firstRunModals, logStream, edition: requireFrontendEditionComposition().dashboard }, dependenciesForMount(mountScope))
    });
    registerPage('forbidden', ForbiddenPage, { factory: (mountScope) => new ForbiddenPage(dependenciesForMount(mountScope)) });
    registerPage('fileExplorer', FileExplorerPage, { factory: (mountScope) => new FileExplorerPage(dependenciesForMount(mountScope)) });
    registerPage('hardware', HardwarePage, {
        factory: (mountScope) => {
            const hardwarePageDependencies = {
                storage: createHardwareStorageAdapter(sharedStorage),
                security: securityApi
            };
            return new HardwarePage(hardwarePageDependencies, dependenciesForMount(mountScope));
        }
    });
    registerPage('help', HelpPage, { factory: (mountScope) => new HelpPage(dependenciesForMount(mountScope)) });
    registerPage('login', LoginPage, { factory: (mountScope) => new LoginPage(dependenciesForMount(mountScope)) });
    registerPage('logs', LogsPage, { factory: (mountScope) => new LogsPage(logStream, dependenciesForMount(mountScope)) });
    registerPage('metrics', MetricsPage, { factory: (mountScope) => new MetricsPage(dependenciesForMount(mountScope)) });
    registerPage('modelDetail', ModelDetailPage, { factory: (mountScope) => new ModelDetailPage(dependenciesForMount(mountScope)) });
    registerPage('models', ModelsPage, {
        factory: (mountScope) => new ModelsPage({ catalogStore }, dependenciesForMount(mountScope))
    });
    registerPage('plugins', PluginsPage, {
        factory: (mountScope) =>
            new PluginsPage(
                {
                    storage: sharedStorage,
                    catalogStore,
                    firstRunModals
                },
                dependenciesForMount(mountScope)
            )
    });
    registerPage('prompts', PromptsPage, { factory: (mountScope) => new PromptsPage(dependenciesForMount(mountScope)) });
    registerPage('search', SearchPage, { factory: (mountScope) => new SearchPage({ searchComponent }, dependenciesForMount(mountScope)) });
    registerPage('settings', SettingsPage, {
        factory: (mountScope) =>
            new SettingsPage(
                {
                    restartOverlay,
                    subscribeModelCatalog: modelCatalogSubscriber,
                    product: requireFrontendEditionComposition().settings,
                    dashboardTitle: requireFrontendEditionComposition().dashboard?.getTitle ?? null
                },
                dependenciesForMount(mountScope)
            )
    });
    registerPage('terminal', TerminalPage, { factory: (mountScope) => new TerminalPage(dependenciesForMount(mountScope)) });
    registerPage('updates', UpdatesPage, {
        factory: (mountScope) => new UpdatesPage({ catalogStore, restartOverlay, product: requireFrontendEditionComposition().updates }, dependenciesForMount(mountScope))
    });
    registerPage('wizard', WizardPage, {
        factory: (mountScope) =>
            new WizardPage(
                {
                    licenseService: getLicenseService()
                },
                dependenciesForMount(mountScope)
            )
    });
    for (const contribution of requireFrontendEditionComposition().pages) {
        registerPage(contribution.id, contribution.pageClass, contribution.options(dependenciesForMount));
    }
};

export { registerPages };
