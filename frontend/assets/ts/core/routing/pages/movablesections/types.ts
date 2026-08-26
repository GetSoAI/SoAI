/* SoAI - Shared routing movable sections contracts [frontend/assets/ts/core/routing/pages/movablesections/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CreateSectionOptions, GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { AutoScroller } from '@core/ui/AutoScroller.ts';
import type { GridAnimator } from '@core/ui/GridAnimator.ts';

type MovableSectionId = string;

interface MovableGridBreakpoint {
    maxWidth: number;
    columns: number;
}

interface MovableBreakpointResponsivePolicy {
    type: 'breakpoints';
    breakpoints: ReadonlyArray<MovableGridBreakpoint>;
}

interface MovableContentScaleResponsivePolicy {
    type: 'content-scale';
    referenceCellWidth: number;
    minimumContentScale: number;
}

type MovableResponsivePolicy = MovableBreakpointResponsivePolicy | MovableContentScaleResponsivePolicy;

interface MovableGridSettings {
    columns: number;
    baseCellHeight: number;
    dragThreshold: number;
    dragScale: number;
    responsive: MovableResponsivePolicy;
}

interface MovableSectionBlueprint {
    layout: GridPosition;
    showSubtitle: boolean;
    controls?: () => TrustedHtml;
}

interface MovableSectionLayoutHost {
    optionalUI: (selector: string, context?: Element | null) => Element | null;
    optionalHTMLElement: (selector: string, context?: Element | null) => HTMLElement | null;
    requireHTMLElement: (selector: string, context?: Element | null) => HTMLElement;
    on: (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;
    updateStyle: (element: Element | null, property: string, value: string) => void;
    updateStyles: (element: Element | null, styles: Record<string, string | null>) => void;
    applyGridPosition: (element: Element, position: GridPosition) => void;
    createSection: (id: string, options?: CreateSectionOptions) => HTMLElement;
    logger: (level: 'debug', message: string, detail?: JsonValue | null | undefined) => void;
}

interface MovableSectionLayoutStorage {
    getLayout: () => JsonValue | null | undefined;
    saveLayout: (layout: JsonValue | null | undefined) => void;
    getHiddenSectionIds: () => string[];
}

interface MovableSectionLayoutConfig<TSectionId extends MovableSectionId> {
    logLabel: string;
    gridSelector: string;
    sectionSelector: string;
    sectionClassName: string;
    sectionIdAttribute: string;
    dragHandleSelector: string;
    invalidDragSelector: string;
    settings: MovableGridSettings;
    isSectionId: (value: string) => value is TSectionId;
    resolveTitle: (sectionId: TSectionId) => string;
    resolveSubtitle: (sectionId: TSectionId) => string;
}

interface MovableSectionLayoutDependencies<TSectionId extends MovableSectionId> {
    host: MovableSectionLayoutHost;
    storage: MovableSectionLayoutStorage;
    config: MovableSectionLayoutConfig<TSectionId>;
}

interface MovableGridMetrics {
    columns: number;
    paddingLeft: number;
    paddingRight: number;
    paddingTop: number;
    paddingBottom: number;
    columnGap: number;
    rowGap: number;
    cellWidth: number;
    cellHeight: number;
    contentScale: number;
}

interface MovableGridSpace {
    width: number;
    paddingLeft: number;
    paddingRight: number;
    paddingTop: number;
    paddingBottom: number;
    columnGap: number;
    rowGap: number;
}

interface MovableGridPresentation {
    collapsed: boolean;
    metrics: MovableGridMetrics;
}

interface MovableDragState<TSectionId extends MovableSectionId> {
    id: TSectionId;
    pointerId: number;
    section: HTMLElement;
    handle: HTMLElement;
    origin: GridPosition;
    startX: number;
    startY: number;
    dragStarted: boolean;
    grabOffsetX: number;
    grabOffsetY: number;
    span: { width: number; height: number };
    previewLayout: Map<string, GridPosition> | null;
    pending: GridPosition | null;
    disposers: Array<() => void>;
}

interface MovableSectionLayoutContext<TSectionId extends MovableSectionId> {
    host: MovableSectionLayoutHost;
    config: MovableSectionLayoutConfig<TSectionId>;
    positions: Map<TSectionId, GridPosition>;
    dragState: MovableDragState<TSectionId> | null;
    sectionDisposers: Array<() => void>;
    gridAnimator: GridAnimator | null;
    autoScroller: AutoScroller | null;
    metrics: MovableGridMetrics | null;
    gridElement: HTMLElement | null;
    currentColumns: number;
    collapsed: boolean;
    locked: boolean;
    refreshMetrics: () => void;
    getDisplayLayout: () => Map<TSectionId, GridPosition>;
    applyLayout: (layout: Map<TSectionId, GridPosition>) => void;
    notifyLayoutChanged: () => void;
    getActiveColumns: () => number;
}

export type { MovableDragState, MovableGridMetrics, MovableGridPresentation, MovableGridSettings, MovableGridSpace, MovableSectionBlueprint, MovableSectionId, MovableSectionLayoutConfig, MovableSectionLayoutContext, MovableSectionLayoutDependencies, MovableSectionLayoutHost, MovableSectionLayoutStorage };
