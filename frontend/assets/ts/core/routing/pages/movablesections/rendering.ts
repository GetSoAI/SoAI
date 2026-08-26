/* SoAI - Shared routing rendering [frontend/assets/ts/core/routing/pages/movablesections/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireDocument } from '@core/environment/public.ts';
import type { CreateSectionOptions, GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { MovableSectionBlueprint, MovableSectionId, MovableSectionLayoutConfig } from '@core/routing/pages/movablesections/types.ts';
import { parseGridPosition } from '@core/routing/pages/movablesections/normalization.ts';

const createMovableSectionElement = <TSectionId extends MovableSectionId>(
    sectionId: TSectionId,
    blueprint: MovableSectionBlueprint,
    position: GridPosition,
    dependencies: {
        config: MovableSectionLayoutConfig<TSectionId>;
        createSection: (id: string, options: CreateSectionOptions) => HTMLElement;
        registerDrag: (section: HTMLElement, id: TSectionId) => void;
        locked: boolean;
        collapsed: boolean;
    }
): HTMLElement => {
    const config: CreateSectionOptions = {
        title: dependencies.config.resolveTitle(sectionId),
        subtitle: dependencies.config.resolveSubtitle(sectionId),
        controls: blueprint.controls ? blueprint.controls() : EMPTY_UI_HTML,
        showSubtitle: blueprint.showSubtitle,
        className: dependencies.config.sectionClassName,
        position
    };
    const section = dependencies.createSection(sectionId, config);
    dependencies.registerDrag(section, sectionId);
    section.classList.toggle('is-locked', dependencies.locked);
    section.classList.toggle('is-collapsed', dependencies.collapsed);
    return section;
};

const renderMovableSections = <TSectionId extends MovableSectionId>(
    blueprints: Map<TSectionId, MovableSectionBlueprint>,
    positions: Map<TSectionId, GridPosition>,
    hiddenElements: Set<TSectionId>,
    config: MovableSectionLayoutConfig<TSectionId>,
    dependencies: {
        createSection: (sectionId: TSectionId, blueprint: MovableSectionBlueprint, position: GridPosition) => HTMLElement;
    }
): { fragment: DocumentFragment; rendered: Array<{ id: TSectionId; section: HTMLElement }> } => {
    const fragment = requireDocument().createDocumentFragment();
    const rendered: Array<{ id: TSectionId; section: HTMLElement }> = [];
    for (const [id, blueprint] of blueprints.entries()) {
        if (hiddenElements.has(id)) {
            continue;
        }
        const defaultLayout = parseGridPosition(blueprint.layout, config.settings.columns);
        if (!defaultLayout) {
            throw new Error(`Movable layout blueprint for section "${id}" is invalid`);
        }
        const layout = positions.get(id) ?? defaultLayout;
        const section = dependencies.createSection(id, blueprint, layout);
        fragment.appendChild(section);
        rendered.push({ id, section });
    }
    return { fragment, rendered };
};

export { createMovableSectionElement, renderMovableSections };
