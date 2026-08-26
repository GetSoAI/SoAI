/* SoAI - Shared route registry mappers [frontend/assets/ts/core/routeregistry/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isNumber } from '@core/typeGuards.ts';
import type { RawRouteDefinition, RouteData, RouteEntry, RouteLayout, RouteSearch, RouteSearchDefinition, RouteSidebar, RouteSidebarDefinition, SidebarBlueprintEntry } from '@core/routeregistry/contracts.ts';

const mapRouteData = (definition: RawRouteDefinition): RouteData => {
    return {
        streams: Object.freeze(filterTrimmedStringArrayValue(definition.data?.streams)),
        resources: Object.freeze(filterTrimmedStringArrayValue(definition.data?.resources)),
        collections: Object.freeze(filterTrimmedStringArrayValue(definition.data?.collections))
    };
};

const mapRouteSidebar = (definition: RouteSidebarDefinition): RouteSidebar => {
    return Object.freeze({
        include: definition.include !== false,
        getLabel: definition.getLabel ?? null,
        icon: definition.icon ?? null,
        section: definition.section ?? null,
        order: isNumber(definition.order) ? definition.order : 0,
        parent: definition.parent ?? null,
        adminOnly: definition.adminOnly === true
    });
};

const mapRouteLayout = (definition: RawRouteDefinition): RouteLayout => {
    return Object.freeze({
        hideSidebar: definition.layout?.hideSidebar === true,
        scrollToTopAction: definition.layout?.scrollToTopAction !== false,
        headerActionHandoff: Object.freeze(filterTrimmedStringArrayValue(definition.layout?.headerActionHandoff))
    });
};

const mapRouteSearch = (definition: RouteSearchDefinition): RouteSearch => {
    return Object.freeze({
        include: definition.include !== false,
        getTitle: definition.getTitle ?? null,
        getDescription: definition.getDescription
    });
};

const createRouteEntry = (definition: RawRouteDefinition): RouteEntry => {
    const data = mapRouteData(definition);
    const sidebar = definition.sidebar ? mapRouteSidebar(definition.sidebar) : null;
    const layout = mapRouteLayout(definition);
    const search = definition.search ? mapRouteSearch(definition.search) : null;
    return Object.freeze({
        id: definition.id,
        path: definition.path,
        component: definition.component,
        getTitle: definition.getTitle,
        auth: Boolean(definition.auth),
        adminOnly: definition.adminOnly === true,
        actions: Object.freeze(filterTrimmedStringArrayValue(definition.actions)),
        data,
        sidebar,
        layout,
        search
    });
};

const cloneEntries = (entries: readonly SidebarBlueprintEntry[]): SidebarBlueprintEntry[] => entries.map((entry) => ({ ...entry }));

export { cloneEntries, createRouteEntry };
