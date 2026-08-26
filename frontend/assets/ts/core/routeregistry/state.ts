/* SoAI - Shared route registry state [frontend/assets/ts/core/routeregistry/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ROUTE_DEFINITIONS_RAW } from '@core/routeregistry/constants.ts';
import { cloneEntries, createRouteEntry } from '@core/routeregistry/mappers.ts';
import type { RawRouteDefinition, RouteDefinition, RouteEntry, RouteRegistry, SidebarBlueprintEntry, SidebarComponentTargets } from '@core/routeregistry/contracts.ts';

interface RouteRegistryState {
    readonly routeDefinitions: readonly RouteDefinition[];
    readonly routeRegistry: RouteRegistry;
    readonly sidebarAdminIds: readonly string[];
    readonly sidebarBlocklist: ReadonlySet<string>;
    readonly sidebarBlueprint: readonly SidebarBlueprintEntry[];
    readonly sidebarTargets: SidebarComponentTargets;
}

let routeRegistryState: RouteRegistryState | null = null;
let contributedRoutes: readonly RawRouteDefinition[] | null = null;

const configureRouteContributions = (routes: readonly RawRouteDefinition[]): void => {
    if (contributedRoutes !== null || routeRegistryState !== null) {
        throw new Error('Route contributions are already configured');
    }
    contributedRoutes = Object.freeze([...routes]);
};

const createRouteRegistryState = (): RouteRegistryState => {
    if (contributedRoutes === null) {
        throw new Error('Route contributions must be configured before route registry access');
    }
    const routeEntries: readonly RouteEntry[] = Object.freeze([...ROUTE_DEFINITIONS_RAW, ...contributedRoutes].map((definition) => createRouteEntry(definition)));
    const routeRegistry: RouteRegistry = Object.freeze(
        routeEntries.reduce<Record<string, RouteEntry>>((registry, entry) => {
            registry[entry.id] = entry;
            return registry;
        }, {})
    );
    const routeDefinitions: readonly RouteDefinition[] = Object.freeze(
        routeEntries.map((entry) =>
            Object.freeze({
                path: entry.path,
                component: entry.component,
                getTitle: entry.getTitle,
                auth: entry.auth,
                adminOnly: entry.adminOnly,
                actions: entry.actions,
                data: entry.data,
                layout: entry.layout,
                search: entry.search
            })
        )
    );
    const sidebarTargets: SidebarComponentTargets = Object.freeze(
        routeEntries.reduce<Record<string, string | null>>((targets, entry) => {
            const sidebar = entry.sidebar;
            if (sidebar?.parent) {
                targets[entry.component] = sidebar.parent;
                return targets;
            }
            if (sidebar?.include) {
                targets[entry.component] = entry.id;
                return targets;
            }
            targets[entry.component] = null;
            return targets;
        }, {})
    );
    const sidebarBlueprint: readonly SidebarBlueprintEntry[] = Object.freeze(
        routeEntries
            .filter((entry): entry is RouteEntry & { sidebar: NonNullable<RouteEntry['sidebar']> } => Boolean(entry.sidebar?.include))
            .sort((firstValue, secondValue) => firstValue.sidebar.order - secondValue.sidebar.order)
            .map((entry) =>
                Object.freeze({
                    type: 'page',
                    id: entry.id,
                    getLabel: entry.sidebar.getLabel,
                    icon: entry.sidebar.icon,
                    section: entry.sidebar.section,
                    order: entry.sidebar.order,
                    adminOnly: entry.sidebar.adminOnly,
                    actions: entry.actions,
                    data: entry.data
                })
            )
    );
    return Object.freeze({
        routeDefinitions,
        routeRegistry,
        sidebarAdminIds: Object.freeze(sidebarBlueprint.filter((entry) => entry.adminOnly).map((entry) => entry.id)),
        sidebarBlocklist: Object.freeze(new Set([...routeEntries.filter((entry) => entry.layout.hideSidebar).map((entry) => entry.path), 'detached'])),
        sidebarBlueprint,
        sidebarTargets
    });
};

const requireRouteRegistryState = (): RouteRegistryState => {
    if (routeRegistryState === null) {
        routeRegistryState = createRouteRegistryState();
    }
    return routeRegistryState;
};

const getRouteRegistry = (): RouteRegistry => requireRouteRegistryState().routeRegistry;

const getRouteDefinitions = (): RouteDefinition[] => requireRouteRegistryState().routeDefinitions.map((definition) => ({ ...definition }));

const getSidebarNavigationBlueprint = (): SidebarBlueprintEntry[] => {
    return cloneEntries(requireRouteRegistryState().sidebarBlueprint);
};

const getSidebarComponentTargets = (): SidebarComponentTargets => {
    return {
        ...requireRouteRegistryState().sidebarTargets
    };
};

const getSidebarBlocklist = (): ReadonlySet<string> => requireRouteRegistryState().sidebarBlocklist;

const getAdminOnlySidebarPages = (): string[] => requireRouteRegistryState().sidebarAdminIds.slice();

export { configureRouteContributions, getAdminOnlySidebarPages, getRouteDefinitions, getRouteRegistry, getSidebarBlocklist, getSidebarComponentTargets, getSidebarNavigationBlueprint };
