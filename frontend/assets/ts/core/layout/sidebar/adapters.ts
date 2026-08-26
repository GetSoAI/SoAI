/* SoAI - Shared frontend layout sidebar adapters [frontend/assets/ts/core/layout/sidebar/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAdminOnlySidebarPages, getSidebarBlocklist, getSidebarComponentTargets, getSidebarNavigationBlueprint } from '@core/routeregistry/service.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { MAIN_STATE_SERVICE_ID } from '@core/indicators/protocols.ts';
import { SidebarBusyIndicatorRegistry } from '@core/layout/sidebar/busyIndicatorRegistry.ts';
import { requireStringRecord, requireStringSet } from '@core/layout/sidebar/foundation.ts';
import { SidebarLinkIndicatorController } from '@core/layout/sidebar/linkIndicator.ts';
import { SidebarPluginIndicatorController, type SidebarStoragePluginIndicatorContract } from '@core/layout/sidebar/pluginIndicator.ts';
import { SidebarVersionController, type SidebarVersionDisplayState, type SidebarVersionDomRefKey } from '@core/layout/sidebar/version.ts';
import { requireSidebarConfigEntries, type SidebarComponentInstance, type SidebarConfigEntry, type SidebarViewHost } from '@core/layout/sidebar/view.ts';

interface SidebarStaticConfig {
    routeComponentMap: Record<string, string>;
    routeBlocklist: Set<string>;
    adminOnlyItems: Set<string>;
    defaultSidebarConfig: ReadonlyArray<SidebarConfigEntry>;
}

interface SidebarRendererHostFactory {
    getMenuElement: () => HTMLElement | null;
    resolveLabel: (cfg: SidebarConfigEntry) => string;
    resolveIconMarkup: (icon: IconName | null | undefined) => Promise<TrustedHtml>;
    waitForComponent: (name: string | null) => Promise<SidebarComponentInstance>;
    updateMainStateIndicator: () => void;
}

interface SidebarAuxControllerFactory {
    getPluginsLink: () => HTMLElement | null;
    getChatLink: () => HTMLElement | null;
    getModelsLink: () => HTMLElement | null;
    getFileExplorerLink: () => HTMLElement | null;
    getAutomationLink: () => HTMLElement | null;
    resolveStorage: () => Promise<SidebarStoragePluginIndicatorContract | null>;
    getDisplayState: () => SidebarVersionDisplayState;
    getDomRef: (key: SidebarVersionDomRefKey) => HTMLElement | null;
}

interface SidebarAuxControllers {
    pluginIndicator: SidebarPluginIndicatorController;
    chatIndicator: SidebarLinkIndicatorController;
    busyIndicatorRegistry: SidebarBusyIndicatorRegistry;
    automationRunningIndicator: SidebarLinkIndicatorController;
    versionController: SidebarVersionController;
}

const createSidebarStaticConfig = (): SidebarStaticConfig => {
    const routeComponentMap = requireStringRecord(getSidebarComponentTargets(), 'Sidebar component targets');
    const routeBlocklist = requireStringSet(getSidebarBlocklist(), 'Sidebar blocklist');
    const adminOnlyItems = new Set(getAdminOnlySidebarPages());

    const sidebarBlueprint = requireSidebarConfigEntries(getSidebarNavigationBlueprint(), 'Sidebar navigation blueprint');
    const defaultSidebarConfigEntries: SidebarConfigEntry[] = [{ type: 'separator' }, ...sidebarBlueprint, { type: 'separator' }, { type: 'component', id: 'main-state', component: MAIN_STATE_SERVICE_ID, section: 'status' }];
    const defaultSidebarConfig: ReadonlyArray<SidebarConfigEntry> = Object.freeze(defaultSidebarConfigEntries);

    return {
        routeComponentMap,
        routeBlocklist,
        adminOnlyItems,
        defaultSidebarConfig
    };
};

const cloneSidebarConfigEntries = (entries: ReadonlyArray<SidebarConfigEntry>): SidebarConfigEntry[] => {
    return entries.map((item) => ({ ...item }));
};

const createSidebarRendererHost = (factory: SidebarRendererHostFactory): SidebarViewHost => {
    return {
        getMenuElement: () => factory.getMenuElement(),
        resolveLabel: (cfg: SidebarConfigEntry) => factory.resolveLabel(cfg),
        resolveIconMarkup: (icon: IconName | null | undefined) => factory.resolveIconMarkup(icon),
        waitForComponent: (name: string | null) => factory.waitForComponent(name),
        updateMainStateIndicator: () => factory.updateMainStateIndicator()
    };
};

const createSidebarAuxControllers = (factory: SidebarAuxControllerFactory): SidebarAuxControllers => {
    const pluginIndicator = new SidebarPluginIndicatorController({
        getPluginsLink: () => factory.getPluginsLink(),
        resolveStorage: () => factory.resolveStorage()
    });
    const chatIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getChatLink() },
        indicatorClassName: 'sidebar-chat-indicator'
    });
    const chatBusyIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getChatLink() },
        indicatorClassName: 'sidebar-busy-indicator'
    });
    const pluginsBusyIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getPluginsLink() },
        indicatorClassName: 'sidebar-busy-indicator'
    });
    const modelsBusyIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getModelsLink() },
        indicatorClassName: 'sidebar-busy-indicator'
    });
    const fileExplorerBusyIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getFileExplorerLink() },
        indicatorClassName: 'sidebar-busy-indicator'
    });
    const busyIndicatorRegistry = new SidebarBusyIndicatorRegistry([
        { pageId: 'chat', controller: chatBusyIndicator },
        { pageId: 'plugins', controller: pluginsBusyIndicator },
        { pageId: 'models', controller: modelsBusyIndicator },
        { pageId: 'fileExplorer', controller: fileExplorerBusyIndicator }
    ]);
    const automationRunningIndicator = new SidebarLinkIndicatorController({
        host: { getLink: () => factory.getAutomationLink() },
        indicatorClassName: 'sidebar-busy-indicator'
    });
    const versionController = new SidebarVersionController({
        getDisplayState: () => factory.getDisplayState(),
        getDomRef: (key) => factory.getDomRef(key)
    });
    return { pluginIndicator, chatIndicator, busyIndicatorRegistry, automationRunningIndicator, versionController };
};

export { cloneSidebarConfigEntries, createSidebarAuxControllers, createSidebarRendererHost, createSidebarStaticConfig };
export type { SidebarAuxControllers, SidebarAuxControllerFactory, SidebarRendererHostFactory, SidebarStaticConfig };
