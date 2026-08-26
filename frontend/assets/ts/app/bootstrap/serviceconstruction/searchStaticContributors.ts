/* SoAI - Bootstrap static search contributors [frontend/assets/ts/app/bootstrap/serviceconstruction/searchStaticContributors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromAuth, createAccessRequirement, createRouteAccessRequirement, createSettingsTabAccessRequirement, type AuthAccessSource } from '@core/access/accessPolicy.ts';
import { i18n } from '@core/i18n/index.ts';
import { getRouteRegistry } from '@core/routeregistry/service.ts';
import type { SearchStaticIndexContributor } from '@core/search/protocols.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { createAdvancedSettingsRenderer, formatConfigPathLabel, NORMAL_TAB_DEFINITIONS, type AnalyzeStructure, type TabDefinition } from '@features/settings/public.ts';
import { HELP_SECTIONS } from '@features/help/public.ts';
import { buildPowerActionSearchMetadata } from '@features/power/public.ts';

interface StaticSearchContributorDependencies {
    apiClient: {
        configs: {
            get(name: string): Promise<ApiResponsePayload>;
        };
    };
    authManager: AuthAccessSource;
}

interface ModalCommand {
    id: string;
    routeId: string;
    getName: () => string;
    getDescription: () => string;
    adminOnly: boolean;
    actions: readonly string[];
    alias: string;
}

const MODAL_COMMANDS: readonly ModalCommand[] = Object.freeze([
    { id: 'add-model', routeId: 'models', getName: () => i18n.t('models.actions.addModel'), getDescription: () => i18n.t('common.modalDescriptions.modelsDownload'), adminOnly: true, actions: ['MODEL_ADMIN'], alias: 'download model install model' },
    { id: 'add-plugin', routeId: 'plugins', getName: () => i18n.t('plugins.actions.installPlugin'), getDescription: () => i18n.t('common.modalDescriptions.pluginsDownload'), adminOnly: true, actions: ['PLUGIN_ADMIN'], alias: 'install plugin download plugin' },
    { id: 'add-automation', routeId: 'automation', getName: () => i18n.t('automation.toolbar.create'), getDescription: () => i18n.t('common.modalDescriptions.automationConfiguration'), adminOnly: false, actions: [], alias: 'create automation schedule task' },
    { id: 'add-mcp-server', routeId: 'settings', getName: () => i18n.t('settings.mcp.servers.actions.addServer'), getDescription: () => i18n.t('common.modalDescriptions.settingsMcpServer'), adminOnly: true, actions: ['MCP_ADMIN'], alias: 'add mcp server model context protocol' },
    { id: 'chat-settings', routeId: 'chat', getName: () => i18n.t('chat.configuration.title'), getDescription: () => i18n.t('common.modalDescriptions.chatConfiguration'), adminOnly: false, actions: [], alias: 'chat settings chat configuration model tools memory interface' }
]);

const createAccessContext = (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>) =>
    createAccessContextFromAuth(dependencies.authManager, {
        soaiOsAvailable: requireFrontendEditionComposition().settings !== null,
        terminalAllowed: grantedActions.has('TERMINAL_USE'),
        grantedActions
    });

const canAccessRoute = (dependencies: StaticSearchContributorDependencies, routeId: string, grantedActions: ReadonlySet<string>): boolean => {
    const route = getRouteRegistry()[routeId];
    if (!route) {
        throw new Error(`Static search contributor requires route "${routeId}"`);
    }
    return canAccessUiSurface(createRouteAccessRequirement(route), createAccessContext(dependencies, grantedActions));
};

const buildNormalSettingsEntries = (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>): SearchItem[] => {
    if (!canAccessRoute(dependencies, 'settings', grantedActions)) {
        return [];
    }
    const context = createAccessContext(dependencies, grantedActions);
    const settingsContribution = requireFrontendEditionComposition().settings;
    const definitions = [...NORMAL_TAB_DEFINITIONS, ...(settingsContribution?.tabs ?? [])];
    return definitions
        .filter((definition) => canAccessUiSurface(createSettingsTabAccessRequirement(definition), context))
        .map((definition): SearchItem => ({
            id: `settings::${definition.id}`,
            name: definition.getLabel(),
            description: i18n.t('search.pages.settings.description'),
            type: 'configuration',
            category: 'configuration',
            identifier: definition.id,
            icon: 'settings',
            alias: `${definition.id} settings configuration section`
        }));
};

const buildAdvancedSectionEntries = (tabs: readonly TabDefinition[]): SearchItem[] =>
    tabs.map((tab): SearchItem => ({
        id: `settings::${tab.id}`,
        name: tab.label,
        description: i18n.t('settings.advancedTitle'),
        type: 'configuration',
        category: 'configuration',
        identifier: tab.id,
        icon: 'settings',
        alias: `${tab.sectionKey ?? tab.id} advanced settings configuration`
    }));

const buildAdvancedTabIdsBySectionKey = (tabs: readonly TabDefinition[]): Map<string, string> => {
    const tabIdBySectionKey = new Map<string, string>();
    for (const tab of tabs) {
        if (tab.sectionKey) {
            tabIdBySectionKey.set(tab.sectionKey, tab.id);
        }
    }
    return tabIdBySectionKey;
};

const buildAdvancedConfigKeyEntries = (structure: AnalyzeStructure, tabs: readonly TabDefinition[]): SearchItem[] => {
    const tabIdBySectionKey = buildAdvancedTabIdsBySectionKey(tabs);
    const entries: SearchItem[] = [];
    for (const section of structure.sections) {
        const tabId = tabIdBySectionKey.get(section.key);
        if (!tabId) {
            throw new Error(`Advanced settings search requires a tab for configuration section "${section.key}"`);
        }
        for (const group of section.groups) {
            for (const setting of group.settings) {
                entries.push({
                    id: `config::${setting.path}`,
                    name: setting.path,
                    description: formatConfigPathLabel(setting.path),
                    type: 'configuration',
                    category: 'configuration',
                    identifier: tabId,
                    configPath: setting.path,
                    icon: 'settings'
                });
            }
        }
    }
    return entries;
};

const buildAdvancedSettingsEntries = async (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>): Promise<SearchItem[]> => {
    if (!dependencies.authManager.isAdmin() || !grantedActions.has('CONFIG_PATCH') || !canAccessRoute(dependencies, 'settings', grantedActions)) {
        return [];
    }
    const config = await dependencies.apiClient.configs.get('core');
    if (!isJsonObject(config)) {
        throw new Error('Advanced settings search requires a core configuration object');
    }
    const renderer = createAdvancedSettingsRenderer({ excludeSections: new Set<string>() });
    const structure = renderer.analyze(config);
    const tabs = renderer.createTabs(structure);
    return [...buildAdvancedSectionEntries(tabs), ...buildAdvancedConfigKeyEntries(structure, tabs)];
};

const buildHelpEntries = (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>): SearchItem[] => {
    if (!canAccessRoute(dependencies, 'help', grantedActions)) {
        return [];
    }
    return HELP_SECTIONS.map((section): SearchItem => ({
        id: `help::${section.id}`,
        name: section.getTitle(),
        description: section.getHeading(),
        type: 'help',
        category: 'help',
        identifier: section.id,
        icon: 'help',
        alias: `${section.id} ${section.getHeading()}`
    }));
};

const buildModalEntries = (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>): SearchItem[] =>
    MODAL_COMMANDS.filter((command) => canAccessRoute(dependencies, command.routeId, grantedActions) && canAccessUiSurface(createAccessRequirement({ authenticated: true, admin: command.adminOnly, actions: command.actions }), createAccessContext(dependencies, grantedActions))).map((command): SearchItem => ({
        id: `modal::${command.id}`,
        name: command.getName(),
        description: command.getDescription(),
        type: 'modal',
        category: 'modal',
        identifier: command.id,
        icon: 'settings',
        alias: command.alias
    }));

const buildPowerActionEntries = (dependencies: StaticSearchContributorDependencies, grantedActions: ReadonlySet<string>): SearchItem[] => {
    if (!canAccessRoute(dependencies, 'power', grantedActions)) {
        return [];
    }
    return buildPowerActionSearchMetadata().map((action): SearchItem => ({
        id: `power::${action.key}`,
        name: action.title,
        description: action.description,
        type: 'power-actions',
        category: 'power-actions',
        identifier: action.key,
        icon: action.icon,
        alias: action.alias
    }));
};

const createSearchStaticContributors = (dependencies: StaticSearchContributorDependencies): readonly SearchStaticIndexContributor[] =>
    Object.freeze([
        {
            id: 'settings-static-search',
            bucket: 'configs',
            index: async ({ grantedActions }) => [...buildNormalSettingsEntries(dependencies, grantedActions), ...(await buildAdvancedSettingsEntries(dependencies, grantedActions))]
        },
        {
            id: 'help-static-search',
            bucket: 'help',
            index: ({ grantedActions }) => buildHelpEntries(dependencies, grantedActions)
        },
        {
            id: 'modal-static-search',
            bucket: 'modals',
            index: ({ grantedActions }) => buildModalEntries(dependencies, grantedActions)
        },
        {
            id: 'power-actions-static-search',
            bucket: 'powerActions',
            index: ({ grantedActions }) => buildPowerActionEntries(dependencies, grantedActions)
        }
    ]);

export { createSearchStaticContributors };
