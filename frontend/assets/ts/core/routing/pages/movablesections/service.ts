/* SoAI - Shared routing movable sections service [frontend/assets/ts/core/routing/pages/movablesections/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import type { MovableDragState, MovableGridMetrics, MovableSectionBlueprint, MovableSectionId, MovableSectionLayoutConfig, MovableSectionLayoutDependencies, MovableSectionLayoutHost, MovableSectionLayoutStorage } from '@core/routing/pages/movablesections/types.ts';
import { cancelMovableSectionDrag, registerMovableSectionDrag } from '@core/routing/pages/movablesections/drag.ts';
import { applyMovableGridLayout, applyMovableGridMetrics, movableGridMetricsEqual, toggleMovableGridMode } from '@core/routing/pages/movablesections/grid.ts';
import { compactLayout, filterLayoutBySectionIds, getDisplayLayout, normalizeLayout, toStoredSectionsMap } from '@core/routing/pages/movablesections/normalization.ts';
import { createInitialMovableGridPresentation, resolveMovableGridMetricsForColumns, resolveMovableGridPresentation, validateMovableGridSettings } from '@core/routing/pages/movablesections/responsive.ts';
import { createMovableSectionElement, renderMovableSections } from '@core/routing/pages/movablesections/rendering.ts';
import { disposeMovableSectionBindings, initializeMovableSectionRuntimeBindings, resetMovableSectionRuntimeBindings, type MovableSectionRuntimeBindingTarget } from '@core/routing/pages/movablesections/runtimeBindings.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { AutoScroller } from '@core/ui/AutoScroller.ts';
import type { GridAnimator } from '@core/ui/GridAnimator.ts';

class MovableSectionLayout<TSectionId extends MovableSectionId> implements MovableSectionRuntimeBindingTarget<TSectionId> {
    host: MovableSectionLayoutHost;
    storage: MovableSectionLayoutStorage;
    config: MovableSectionLayoutConfig<TSectionId>;
    positions: Map<TSectionId, GridPosition>;
    gridElement: HTMLElement | null;
    metrics: MovableGridMetrics | null;
    dragState: MovableDragState<TSectionId> | null;
    sectionDisposers: Array<() => void>;
    savedPositions: Map<TSectionId, GridPosition>;
    changeListener: (() => void) | null;
    collapsed: boolean;
    locked: boolean;
    responsiveDisposers: Array<() => void>;
    gridAnimator: GridAnimator | null;
    autoScroller: AutoScroller | null;
    blueprints: Map<TSectionId, MovableSectionBlueprint>;
    visibleSectionIds: Set<TSectionId>;
    currentColumns: number;

    constructor({ host, storage, config }: MovableSectionLayoutDependencies<TSectionId>) {
        validateMovableGridSettings(config.settings);
        this.host = host;
        this.storage = storage;
        this.config = config;
        this.positions = new Map();
        this.gridElement = null;
        this.metrics = null;
        this.dragState = null;
        this.sectionDisposers = [];
        this.savedPositions = new Map();
        this.changeListener = null;
        this.collapsed = false;
        this.locked = false;
        this.responsiveDisposers = [];
        this.gridAnimator = null;
        this.autoScroller = null;
        this.blueprints = new Map();
        this.visibleSectionIds = new Set();
        this.currentColumns = config.settings.columns;
    }

    setLocked(locked: boolean): void {
        this.locked = locked;
        if (this.locked) {
            cancelMovableSectionDrag(this);
        }
        if (!this.gridElement) return;
        const sections = dom.resolveAll(this.config.sectionSelector, this.gridElement);
        Array.from(sections).forEach((section: Element): void => {
            if (section instanceof HTMLElement) {
                section.classList.toggle('is-locked', this.locked);
            }
        });
    }

    load(blueprints: ReadonlyMap<TSectionId, MovableSectionBlueprint>): void {
        this.blueprints = new Map(blueprints);
        const stored = this.storage.getLayout();
        const storedLayout = isObject(stored) ? stored : null;
        const storedSections = storedLayout ? storedLayout['sections'] : null;
        const saved = toStoredSectionsMap(storedSections, this.config.isSectionId);
        this.positions = normalizeLayout(saved, this.blueprints, this.config.settings.columns);
        this.savedPositions = cloneMovablePositions(this.positions);
    }

    initialize(): void {
        initializeMovableSectionRuntimeBindings(this);
    }

    renderSections(): { fragment: DocumentFragment; rendered: Array<{ id: TSectionId; section: HTMLElement }> } {
        cancelMovableSectionDrag(this);
        disposeMovableSectionBindings(this);
        const hiddenElements = new Set<TSectionId>(this.storage.getHiddenSectionIds().filter((value: string): value is TSectionId => this.config.isSectionId(value) && this.blueprints.has(value)));
        const result = renderMovableSections(this.blueprints, this.positions, hiddenElements, this.config, {
            createSection: (sectionId: TSectionId, blueprint: MovableSectionBlueprint, position: GridPosition): HTMLElement => this.createSection(sectionId, blueprint, position)
        });
        this.visibleSectionIds = new Set(result.rendered.map(({ id }) => id));
        return result;
    }

    createSection(id: TSectionId, blueprint: MovableSectionBlueprint, layout: GridPosition): HTMLElement {
        return createMovableSectionElement(id, blueprint, layout, {
            config: this.config,
            createSection: (sectionId: string, options) => this.host.createSection(sectionId, options),
            registerDrag: (section: HTMLElement, sectionId: TSectionId): void => registerMovableSectionDrag(this, section, sectionId),
            locked: this.locked,
            collapsed: this.collapsed
        });
    }

    applyInitialLayout(): void {
        this.applyLayout(this.getDisplayLayout());
    }

    updateResponsiveLayout(): void {
        if (!this.gridElement) {
            return;
        }
        const presentation = resolveMovableGridPresentation(this.gridElement, this.config.settings);
        if (!presentation) {
            return;
        }
        const columnsChanged = presentation.metrics.columns !== this.currentColumns;
        const collapsedChanged = presentation.collapsed !== this.collapsed;
        const metricsChanged = !movableGridMetricsEqual(this.metrics, presentation.metrics);
        if (!columnsChanged && !collapsedChanged && !metricsChanged) {
            return;
        }
        if (this.dragState) {
            cancelMovableSectionDrag(this);
        }
        this.currentColumns = presentation.metrics.columns;
        this.collapsed = presentation.collapsed;
        if (collapsedChanged) {
            this.toggleGridMode(this.collapsed);
        }
        if (columnsChanged || collapsedChanged) {
            this.applyLayout(this.getDisplayLayout(), presentation.metrics);
            this.notifyLayoutChanged();
            return;
        }
        this.commitMetrics(presentation.metrics);
    }

    applyLayout(layout: Map<TSectionId, GridPosition>, metrics: MovableGridMetrics | null = null): void {
        const gridElement = this.gridElement;
        if (!gridElement) return;
        applyMovableGridLayout(gridElement, layout, {
            sectionIdAttribute: this.config.sectionIdAttribute,
            collapsedClassName: 'is-collapsed',
            updateStyle: (element, property, value) => this.host.updateStyle(element, property, value),
            applyGridPosition: (element, position) => this.host.applyGridPosition(element, position)
        });
        if (metrics) {
            this.commitMetrics(metrics);
            return;
        }
        this.refreshMetrics();
    }

    toggleGridMode(collapsed: boolean): void {
        const gridElement = this.gridElement;
        if (!gridElement) return;
        toggleMovableGridMode(gridElement, collapsed, {
            sectionSelector: this.config.sectionSelector,
            collapsedClassName: 'is-collapsed',
            updateStyle: (element, property, value) => this.host.updateStyle(element, property, value)
        });
    }

    getDisplayLayout(): Map<TSectionId, GridPosition> {
        const requiresVisibleProjection = this.config.settings.responsive.type === 'content-scale' && this.currentColumns !== this.config.settings.columns;
        const source = requiresVisibleProjection ? filterLayoutBySectionIds(this.positions, this.visibleSectionIds) : this.positions;
        return getDisplayLayout(source, this.currentColumns, this.collapsed, this.config.settings.columns);
    }

    refreshMetrics(): void {
        const grid = this.gridElement;
        if (!grid) return;
        const metrics = resolveMovableGridMetricsForColumns(grid, this.config.settings, this.currentColumns);
        if (metrics) {
            this.commitMetrics(metrics);
        }
    }

    saveLayout(): void {
        cancelMovableSectionDrag(this);
        this.positions = compactLayout(this.positions, this.config.settings.columns);
        this.applyLayout(this.getDisplayLayout());
        const sections: Record<string, JsonValue> = {};
        for (const [id, position] of this.positions.entries()) {
            sections[id] = { x: position.x, y: position.y, width: position.width, height: position.height };
        }
        this.storage.saveLayout({ sections });
        this.savedPositions = cloneMovablePositions(this.positions);
        this.notifyLayoutChanged();
    }

    hasUnsavedChanges(): boolean {
        return !movablePositionsEqual(this.positions, this.savedPositions);
    }

    isEditableLayoutMode(): boolean {
        return this.currentColumns === this.config.settings.columns && !this.collapsed;
    }

    setChangeListener(listener: (() => void) | null): void {
        this.changeListener = listener;
    }

    notifyLayoutChanged(): void {
        this.changeListener?.();
    }

    getActiveColumns(): number {
        return this.currentColumns;
    }

    initializeResponsiveLayout(): void {
        const grid = this.gridElement;
        if (!grid) {
            throw new Error('Movable grid must exist before responsive initialization');
        }
        const presentation = resolveMovableGridPresentation(grid, this.config.settings) ?? createInitialMovableGridPresentation(this.config.settings);
        this.currentColumns = presentation.metrics.columns;
        this.collapsed = presentation.collapsed;
        this.toggleGridMode(this.collapsed);
        this.commitMetrics(presentation.metrics);
    }

    cancelDrag(): void {
        cancelMovableSectionDrag(this);
    }

    destroy(): void {
        resetMovableSectionRuntimeBindings(this);
        this.changeListener = null;
        this.positions.clear();
        this.savedPositions.clear();
        this.visibleSectionIds.clear();
    }

    private commitMetrics(metrics: MovableGridMetrics): void {
        const grid = this.gridElement;
        if (!grid) {
            return;
        }
        if (!movableGridMetricsEqual(this.metrics, metrics)) {
            applyMovableGridMetrics(grid, metrics, {
                updateStyles: (element, styles) => this.host.updateStyles(element, styles)
            });
        }
        this.metrics = metrics;
    }
}

const cloneMovablePositions = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>): Map<TSectionId, GridPosition> => {
    const cloned = new Map<TSectionId, GridPosition>();
    for (const [id, position] of source.entries()) {
        cloned.set(id, { ...position });
    }
    return cloned;
};

const movablePositionsEqual = <TSectionId extends MovableSectionId>(left: Map<TSectionId, GridPosition>, right: Map<TSectionId, GridPosition>): boolean => {
    if (left.size !== right.size) {
        return false;
    }
    for (const [id, leftPosition] of left.entries()) {
        const rightPosition = right.get(id);
        if (!rightPosition) {
            return false;
        }
        const positionsMatch = leftPosition.x === rightPosition.x && leftPosition.y === rightPosition.y && leftPosition.width === rightPosition.width && leftPosition.height === rightPosition.height;
        if (!positionsMatch) {
            return false;
        }
    }
    return true;
};

export { MovableSectionLayout };
