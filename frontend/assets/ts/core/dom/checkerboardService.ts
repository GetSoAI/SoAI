/* SoAI - Shared DOM checkerboard service [frontend/assets/ts/core/dom/checkerboardService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { CHECKERBOARD_CLASS_PAIR, resolveCheckerboardClass, type CheckerboardClassName } from '@core/dom/checkerboardAssignment.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';

interface CheckerboardServiceDependencies {
    createResourceTracker: () => ResourceTracker;
    getDomWindow: () => Window;
    generateSecureId: (prefix: string) => string;
    dom: {
        addClass: (element: Element, classes: string | string[]) => void;
        removeClass: (element: Element, classes: string | string[]) => void;
        getData: (element: Element, name: string) => string | null;
        setData: (element: Element, name: string, value: string) => void;
    };
}

interface CheckerboardObserverEntry {
    observer: MutationObserver;
    container: Element;
    itemSelector: string;
    frameId: number | null;
    absoluteIndexOffset: number;
}

class CheckerboardService {
    observers: Map<string, CheckerboardObserverEntry>;
    resizeDebounceTimer: number | null;
    resizeDebounceDelay: number;
    resources: ResourceTracker;
    #dependencies: CheckerboardServiceDependencies;
    #lastSignatures: Map<string, string>;
    #lastItems: Map<string, Element[]>;
    #lastAssignments: Map<string, CheckerboardClassName[]>;

    constructor(dependencies: CheckerboardServiceDependencies) {
        this.#dependencies = dependencies;
        this.observers = new Map();
        this.resizeDebounceTimer = null;
        this.resizeDebounceDelay = 150;
        this.resources = dependencies.createResourceTracker();
        this.#lastSignatures = new Map();
        this.#lastItems = new Map();
        this.#lastAssignments = new Map();
        const win = dependencies.getDomWindow();
        this.resources.addEventListener(win, 'resize', () => this.#handleGlobalResize());
        this.resources.addEventListener(win, INTERFACE_SCALE_CHANGED_EVENT, () => this.#handleGlobalResize());
    }

    applyCheckerboard(container: Element, itemSelector: string, absoluteIndexOffset: number = 0): void {
        if (!container) throw new Error('Container element is required');

        const containerId = this.getContainerId(container);
        const existing = this.observers.get(containerId);
        if (existing && existing.container === container && existing.itemSelector === itemSelector) {
            existing.absoluteIndexOffset = this.#normalizeAbsoluteIndexOffset(absoluteIndexOffset);
            this.updateCheckerboard(container, itemSelector, existing.absoluteIndexOffset);
            return;
        }
        this.disconnect(containerId);

        const observer = new MutationObserver(() => {
            this.updateCheckerboard(container, itemSelector);
        });

        observer.observe(container, {
            childList: true,
            subtree: false
        });

        this.observers.set(containerId, {
            observer,
            container,
            itemSelector,
            frameId: null,
            absoluteIndexOffset: this.#normalizeAbsoluteIndexOffset(absoluteIndexOffset)
        });

        this.updateCheckerboard(container, itemSelector, absoluteIndexOffset);
    }

    scheduleUpdate(container: Element, itemSelector: string): void {
        const containerId = this.getContainerId(container);
        const entry = this.observers.get(containerId);
        if (!entry) {
            this.updateCheckerboard(container, itemSelector);
            return;
        }
        if (entry.frameId !== null) {
            return;
        }
        entry.frameId = this.#dependencies.getDomWindow().requestAnimationFrame(() => {
            entry.frameId = null;
            this.updateCheckerboard(container, itemSelector);
        });
    }

    updateCheckerboard(container: Element, itemSelector: string, absoluteIndexOffset?: number): void {
        const items = Array.from(container.querySelectorAll(itemSelector));

        const containerId = this.getContainerId(container);
        const entry = this.observers.get(containerId);
        if (absoluteIndexOffset !== undefined && entry) entry.absoluteIndexOffset = this.#normalizeAbsoluteIndexOffset(absoluteIndexOffset);
        const resolvedOffset = absoluteIndexOffset === undefined ? (entry?.absoluteIndexOffset ?? 0) : this.#normalizeAbsoluteIndexOffset(absoluteIndexOffset);
        if (items.length === 0) {
            this.#lastSignatures.delete(containerId);
            this.#lastItems.delete(containerId);
            this.#lastAssignments.delete(containerId);
            return;
        }
        this.#reapplyKnownAssignments(containerId, items);
        const columns = this.#resolveColumnCount(container);
        const classSignature = items.map((item) => this.#resolveStableClassSignature(item)).join('|');
        const signature = `${itemSelector}:${items.length}:${container.clientWidth}:${columns}:${resolvedOffset}:${classSignature}`;
        const hasAppliedClasses = items.every((item) => item.classList.contains('checkerboard-light') || item.classList.contains('checkerboard-dark'));
        if (hasAppliedClasses && this.#lastSignatures.get(containerId) === signature && this.#itemsMatchLastRun(containerId, items)) {
            return;
        }
        this.#lastSignatures.set(containerId, signature);
        this.#lastItems.set(containerId, items);

        const assignments = this.#computeAssignments(container, itemSelector, items, columns, resolvedOffset);
        items.forEach((item, index) => {
            const assigned = assignments[index];
            if (assigned !== undefined && !item.classList.contains(assigned)) {
                this.#dependencies.dom.removeClass(item, CHECKERBOARD_CLASS_PAIR);
                this.#dependencies.dom.addClass(item, assigned);
            }
        });
        this.#lastAssignments.set(containerId, assignments);
    }

    groupItemsIntoRows(items: Element[], containerRect: GeometryBox): Element[][] {
        const rows: Element[][] = [];
        let currentRow: Element[] = [];
        let currentRowTop: number | null = null;
        const tolerance = 5;

        items.forEach((item) => {
            const itemRect = measureLayoutBox(item);
            const itemTop = itemRect.top - containerRect.top;

            if (currentRowTop === null) {
                currentRowTop = itemTop;
                currentRow.push(item);
            } else if (Math.abs(itemTop - currentRowTop) < tolerance) {
                currentRow.push(item);
            } else {
                rows.push(currentRow);
                currentRow = [item];
                currentRowTop = itemTop;
            }
        });

        if (currentRow.length > 0) {
            rows.push(currentRow);
        }

        return rows;
    }

    #computeAssignments(container: Element, itemSelector: string, items: Element[], columns: number, absoluteIndexOffset: number): CheckerboardClassName[] {
        const allTableRows = items.every((item) => item instanceof HTMLTableRowElement);
        if (allTableRows) {
            return items.map((_item, index) => resolveCheckerboardClass(absoluteIndexOffset + index));
        }

        if (columns > 0) {
            const start: CheckerboardClassName = itemSelector === '.ui-page-header-stats__card' ? 'checkerboard-light' : 'checkerboard-dark';
            return items.map((_item, index) => resolveCheckerboardClass(absoluteIndexOffset + index, { columns, start }));
        }

        const containerRect = measureLayoutBox(container);
        const rows = this.groupItemsIntoRows(items, containerRect);
        const rowAssignments = new Map<Element, CheckerboardClassName>();
        rows.forEach((rowItems, rowIndex) => {
            const invertPattern = itemSelector !== '.ui-page-header-stats__card';
            const startWithLight = invertPattern ? rowIndex % 2 !== 0 : rowIndex % 2 === 0;
            rowItems.forEach((item, colIndex) => {
                const isLight = startWithLight ? colIndex % 2 === 0 : colIndex % 2 !== 0;
                rowAssignments.set(item, isLight ? 'checkerboard-light' : 'checkerboard-dark');
            });
        });
        return items.map((item) => {
            const assigned = rowAssignments.get(item);
            if (!assigned) {
                throw new Error('Checkerboard assignment missing for grouped item');
            }
            return assigned;
        });
    }

    #normalizeAbsoluteIndexOffset(value: number): number {
        return Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
    }

    #reapplyKnownAssignments(containerId: string, items: readonly Element[]): void {
        const assignments = this.#lastAssignments.get(containerId);
        if (!assignments || assignments.length !== items.length) {
            return;
        }
        items.forEach((item, index) => {
            const assigned = assignments[index];
            if (assigned !== undefined && !item.classList.contains(assigned)) {
                this.#dependencies.dom.removeClass(item, CHECKERBOARD_CLASS_PAIR);
                this.#dependencies.dom.addClass(item, assigned);
            }
        });
    }

    #resolveColumnCount(container: Element): number {
        const style = this.#dependencies.getDomWindow().getComputedStyle(container);
        const templateColumns = style.gridTemplateColumns.trim();
        if (templateColumns && templateColumns !== 'none') {
            const columns = templateColumns.split(/\s+/).filter((entry) => entry.trim().length > 0).length;
            if (columns > 0) {
                return columns;
            }
        }
        return 0;
    }

    #resolveStableClassSignature(item: Element): string {
        return Array.from(item.classList)
            .filter((className) => className !== 'checkerboard-light' && className !== 'checkerboard-dark')
            .join('.');
    }

    #itemsMatchLastRun(containerId: string, items: readonly Element[]): boolean {
        const previous = this.#lastItems.get(containerId);
        if (!previous || previous.length !== items.length) {
            return false;
        }
        return previous.every((item, index) => item === items[index]);
    }

    handleGlobalResize(): void {
        this.#handleGlobalResize();
    }

    #handleGlobalResize(): void {
        if (this.resizeDebounceTimer) {
            this.#dependencies.getDomWindow().clearTimeout(this.resizeDebounceTimer);
        }

        this.resizeDebounceTimer = this.#dependencies.getDomWindow().setTimeout(() => {
            this.resizeDebounceTimer = null;
            this.observers.forEach(({ container, itemSelector }) => {
                this.scheduleUpdate(container, itemSelector);
            });
        }, this.resizeDebounceDelay);
    }

    disconnect(containerId: string): void {
        const entry = this.observers.get(containerId);
        if (entry) {
            if (entry.frameId !== null) {
                this.#dependencies.getDomWindow().cancelAnimationFrame(entry.frameId);
            }
            entry.observer.disconnect();
            this.observers.delete(containerId);
            this.#lastSignatures.delete(containerId);
            this.#lastItems.delete(containerId);
            this.#lastAssignments.delete(containerId);
        }
    }

    disconnectAll(): void {
        this.observers.forEach(({ observer, frameId }) => {
            if (frameId !== null) {
                this.#dependencies.getDomWindow().cancelAnimationFrame(frameId);
            }
            observer.disconnect();
        });
        this.observers.clear();
        this.#lastSignatures.clear();
        this.#lastItems.clear();
        this.#lastAssignments.clear();
    }

    getContainerId(container: Element): string {
        let id = this.#dependencies.dom.getData(container, 'checkerboardId');
        if (id) return id;
        const generated = this.#dependencies.generateSecureId('checkerboard');
        this.#dependencies.dom.setData(container, 'checkerboardId', generated);
        return generated;
    }
}

const createCheckerboardService = (dependencies: CheckerboardServiceDependencies): CheckerboardService => new CheckerboardService(dependencies);

export { CheckerboardService, createCheckerboardService };
