/* SoAI - Shared route registry contracts [frontend/assets/ts/core/routeregistry/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface RouteData {
    readonly streams: readonly string[];
    readonly resources: readonly string[];
    readonly collections: readonly string[];
}

interface RouteSidebar {
    readonly include: boolean;
    readonly getLabel: (() => string) | null;
    readonly icon: IconName | null;
    readonly section: string | null;
    readonly order: number;
    readonly parent: string | null;
    readonly adminOnly: boolean;
}

interface RouteLayout {
    readonly hideSidebar: boolean;
    readonly scrollToTopAction: boolean;
    readonly headerActionHandoff: readonly string[];
}

interface RouteSearch {
    readonly include: boolean;
    readonly getTitle: (() => string) | null;
    readonly getDescription: () => string;
}

interface RouteDataDefinition {
    streams?: string[];
    resources?: string[];
    collections?: string[];
}

interface RouteSidebarDefinition {
    include?: boolean;
    getLabel?: (() => string) | null;
    icon?: IconName | null;
    section?: string | null;
    order?: number;
    parent?: string | null;
    adminOnly?: boolean;
}

interface RouteLayoutDefinition {
    hideSidebar?: boolean;
    scrollToTopAction?: boolean;
    headerActionHandoff?: readonly string[];
}

interface RouteSearchDefinition {
    include?: boolean;
    getTitle?: (() => string) | null;
    getDescription: () => string;
}

interface RawRouteDefinition {
    id: string;
    path: string;
    component: string;
    getTitle: () => string;
    auth: boolean;
    adminOnly?: boolean;
    actions?: string[];
    data?: RouteDataDefinition;
    sidebar?: RouteSidebarDefinition | null;
    layout?: RouteLayoutDefinition;
    search?: RouteSearchDefinition | null;
}

interface RouteEntry {
    readonly id: string;
    readonly path: string;
    readonly component: string;
    readonly getTitle: () => string;
    readonly auth: boolean;
    readonly adminOnly: boolean;
    readonly actions: readonly string[];
    readonly data: RouteData;
    readonly sidebar: RouteSidebar | null;
    readonly layout: RouteLayout;
    readonly search: RouteSearch | null;
}

interface SidebarBlueprintEntry {
    readonly type: 'page';
    readonly id: string;
    readonly getLabel: (() => string) | null;
    readonly icon: IconName | null;
    readonly section: string | null;
    readonly order: number;
    readonly adminOnly: boolean;
    readonly actions: readonly string[];
    readonly data: RouteData;
}

interface RouteDefinition {
    path: string;
    component: string;
    getTitle: () => string;
    auth: boolean;
    adminOnly: boolean;
    actions: readonly string[];
    data: RouteData;
    layout: RouteLayout;
    search: RouteSearch | null;
}

type RouteRegistry = { readonly [key: string]: RouteEntry };
type SidebarComponentTargets = { readonly [key: string]: string | null };

export type { RawRouteDefinition, RouteData, RouteDataDefinition, RouteDefinition, RouteEntry, RouteLayout, RouteLayoutDefinition, RouteRegistry, RouteSearch, RouteSearchDefinition, RouteSidebar, RouteSidebarDefinition, SidebarBlueprintEntry, SidebarComponentTargets };
