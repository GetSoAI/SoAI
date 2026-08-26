/* SoAI - Shared layout busy indicator registry [frontend/assets/ts/core/layout/sidebar/busyIndicatorRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { SidebarLinkIndicatorController } from '@core/layout/sidebar/linkIndicator.ts';

type SidebarBusyPageId = 'chat' | 'plugins' | 'models' | 'fileExplorer';

interface SidebarBusyIndicatorEntry {
    pageId: SidebarBusyPageId;
    controller: SidebarLinkIndicatorController;
}

class SidebarBusyIndicatorRegistry {
    readonly #controllers: Map<SidebarBusyPageId, SidebarLinkIndicatorController> = new Map();
    readonly #sources: Map<SidebarBusyPageId, Set<string>> = new Map();

    constructor(entries: readonly SidebarBusyIndicatorEntry[]) {
        for (const entry of entries) {
            if (this.#controllers.has(entry.pageId)) {
                throw new Error(`Duplicate sidebar busy indicator page: ${entry.pageId}`);
            }
            this.#controllers.set(entry.pageId, entry.controller);
            this.#sources.set(entry.pageId, new Set<string>());
        }
    }

    setBusy(pageId: SidebarBusyPageId, sourceId: string, active: boolean): void {
        const sources = this.#requireSources(pageId);
        const normalizedSourceId = toTrimmedString(sourceId);
        if (!normalizedSourceId) {
            throw new Error(`Sidebar busy source id is required for ${pageId}`);
        }
        if (active) {
            sources.add(normalizedSourceId);
        } else {
            sources.delete(normalizedSourceId);
        }
        this.#updatePage(pageId);
    }

    replacePageSources(pageId: SidebarBusyPageId, sourceIds: ReadonlySet<string>): void {
        const sources = this.#requireSources(pageId);
        sources.clear();
        for (const sourceId of sourceIds) {
            const normalizedSourceId = toTrimmedString(sourceId);
            if (!normalizedSourceId) {
                throw new Error(`Sidebar busy source id is required for ${pageId}`);
            }
            sources.add(normalizedSourceId);
        }
        this.#updatePage(pageId);
    }

    clearSourceFromPages(sourceId: string, pageIds: readonly SidebarBusyPageId[]): void {
        const normalizedSourceId = toTrimmedString(sourceId);
        if (!normalizedSourceId) {
            throw new Error('Sidebar busy source id is required');
        }
        for (const pageId of pageIds) {
            this.#requireSources(pageId).delete(normalizedSourceId);
            this.#updatePage(pageId);
        }
    }

    hasPageBusy(pageId: SidebarBusyPageId): boolean {
        return this.#requireSources(pageId).size > 0;
    }

    updateIndicators(): void {
        for (const pageId of this.#controllers.keys()) {
            this.#updatePage(pageId);
        }
    }

    clear(): void {
        for (const [pageId, sources] of this.#sources.entries()) {
            sources.clear();
            this.#updatePage(pageId);
        }
    }

    #requireSources(pageId: SidebarBusyPageId): Set<string> {
        const sources = this.#sources.get(pageId);
        if (!sources) {
            throw new Error(`Sidebar busy indicator is not registered for ${pageId}`);
        }
        return sources;
    }

    #updatePage(pageId: SidebarBusyPageId): void {
        const controller = this.#controllers.get(pageId);
        if (!controller) {
            throw new Error(`Sidebar busy indicator is not registered for ${pageId}`);
        }
        controller.setVisible(this.#requireSources(pageId).size > 0);
    }
}

export { SidebarBusyIndicatorRegistry };
export type { SidebarBusyIndicatorEntry, SidebarBusyPageId };
