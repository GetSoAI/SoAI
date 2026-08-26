/* SoAI - Shared routing panel layout controller [frontend/assets/ts/core/routing/pages/movablesections/panelLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MovableLayoutEditController } from '@core/routing/pages/movablesections/layoutEditController.ts';
import { MovableSectionLayout } from '@core/routing/pages/movablesections/service.ts';
import type { MovableSectionBlueprint, MovableSectionId, MovableSectionLayoutConfig, MovableSectionLayoutHost, MovableSectionLayoutStorage } from '@core/routing/pages/movablesections/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface MovablePanelBlueprint extends MovableSectionBlueprint {
    rootId: string;
    className: string;
    content: TrustedHtml;
}

interface MovablePanelLayoutHost extends MovableSectionLayoutHost {
    replaceElementContent(target: Element, content: TrustedHtml | DocumentFragment, options?: { escape?: boolean }): void;
    flushDOMUpdates(): void;
}

interface MovablePanelLayoutControllerDependencies<TPanelId extends MovableSectionId> {
    host: MovablePanelLayoutHost;
    storage: MovableSectionLayoutStorage;
    config: MovableSectionLayoutConfig<TPanelId>;
    contextId: string;
    saveUnitId: string;
    requestContextLabel: string;
    isCustomizationDisabled: () => boolean;
}

class MovablePanelLayoutController<TPanelId extends MovableSectionId, TBlueprint extends MovablePanelBlueprint> {
    readonly #host: MovablePanelLayoutHost;
    readonly #layout: MovableSectionLayout<TPanelId>;
    readonly #editController: MovableLayoutEditController<TPanelId>;
    #blueprints: Map<TPanelId, TBlueprint> = new Map();

    constructor(dependencies: MovablePanelLayoutControllerDependencies<TPanelId>) {
        this.#host = dependencies.host;
        this.#layout = new MovableSectionLayout({
            host: dependencies.host,
            storage: dependencies.storage,
            config: dependencies.config
        });
        this.#editController = new MovableLayoutEditController({
            layout: this.#layout,
            contextId: dependencies.contextId,
            saveUnitId: dependencies.saveUnitId,
            requestContextLabel: dependencies.requestContextLabel,
            isCustomizationDisabled: dependencies.isCustomizationDisabled
        });
    }

    load(blueprints: ReadonlyMap<TPanelId, TBlueprint>): void {
        this.#blueprints = new Map(blueprints);
        this.#layout.load(this.#blueprints);
        this.#layout.initialize();
        this.#editController.initialize();
        this.#renderSections();
    }

    hasPanel(panelId: TPanelId): boolean {
        return this.#blueprints.has(panelId);
    }

    hasChanges(): boolean {
        return this.#editController.hasChanges();
    }

    onResponsiveLayout(): void {
        this.#layout.updateResponsiveLayout();
        this.#editController.sync();
    }

    destroy(): void {
        this.#editController.destroy();
        this.#layout.destroy();
        this.#blueprints.clear();
    }

    #renderSections(): void {
        const grid = this.#host.requireHTMLElement(this.#layout.config.gridSelector);
        const renderedSections = this.#layout.renderSections();
        this.#host.replaceElementContent(grid, renderedSections.fragment, { escape: false });
        for (const rendered of renderedSections.rendered) {
            this.#hydrateSection(rendered.id, rendered.section);
        }
        this.#host.flushDOMUpdates();
        this.#layout.applyInitialLayout();
    }

    #hydrateSection(sectionId: TPanelId, section: HTMLElement): void {
        const blueprint = this.#blueprints.get(sectionId);
        if (!blueprint) {
            throw new Error(`Movable panel blueprint missing for ${sectionId}`);
        }
        section.id = blueprint.rootId;
        this.#addClassNames(section, blueprint.className);
        const content = this.#host.requireHTMLElement(`#${sectionId}-content`, section);
        this.#host.replaceElementContent(content, blueprint.content, { escape: false });
    }

    #addClassNames(element: HTMLElement, classNames: string): void {
        for (const className of classNames.split(' ')) {
            if (className) {
                element.classList.add(className);
            }
        }
    }
}

export { MovablePanelLayoutController };
export type { MovablePanelBlueprint, MovablePanelLayoutControllerDependencies, MovablePanelLayoutHost };
