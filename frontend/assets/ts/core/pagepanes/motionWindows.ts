/* SoAI - Tiled pane window geometry for compositor-only motion [frontend/assets/ts/core/pagepanes/motionWindows.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GeometryBox } from '@core/layout/elementGeometry.ts';

interface PagePaneSpan {
    readonly left: number;
    readonly right: number;
}

type PagePaneAnchor = 'left' | 'right';

interface PagePaneLayerMotion {
    readonly root: readonly [number, number];
    readonly frame: readonly [number, number];
    readonly content: readonly [number, number];
    readonly lift: number;
}

interface PagePaneLayerShift {
    readonly root: number;
    readonly frame: number;
    readonly content: number;
}

const PAGE_PANE_WINDOW_TOLERANCE_PX = 0.5;

const toPagePaneSpan = (box: GeometryBox): PagePaneSpan => ({ left: box.left, right: box.right });

const collapsePagePaneSpan = (position: number): PagePaneSpan => ({ left: position, right: position });

const resolvePagePaneAnchor = (point: number, span: PagePaneSpan): PagePaneAnchor => (Math.abs(point - span.right) <= Math.abs(point - span.left) ? 'left' : 'right');

const resolvePagePaneLayerShift = (box: GeometryBox, window: PagePaneSpan, anchor: PagePaneAnchor, rtl: boolean, bounded: boolean): PagePaneLayerShift => {
    const contentLeft = anchor === 'left' ? window.left : window.right - box.width;
    const rootLeft = rtl ? window.right - box.width : window.left;
    const frameLeft = bounded ? rootLeft : rtl ? window.left : window.right - box.width;
    return { root: rootLeft - box.left, frame: frameLeft - rootLeft, content: contentLeft - frameLeft };
};

const isPagePaneWindowBounded = (spans: readonly PagePaneSpan[], bounds: GeometryBox, rtl: boolean): boolean => spans.every((span) => (rtl ? span.left <= bounds.left + PAGE_PANE_WINDOW_TOLERANCE_PX : span.right >= bounds.right - PAGE_PANE_WINDOW_TOLERANCE_PX));

const resolvePagePaneLayerMotion = (box: GeometryBox, origin: PagePaneSpan, target: PagePaneSpan, anchor: PagePaneAnchor, bounds: GeometryBox, rtl: boolean, lift: number): PagePaneLayerMotion | null => {
    const bounded = isPagePaneWindowBounded([origin, target], bounds, rtl);
    const first = resolvePagePaneLayerShift(box, origin, anchor, rtl, bounded);
    const last = resolvePagePaneLayerShift(box, target, anchor, rtl, bounded);
    const motion: PagePaneLayerMotion = { root: [first.root, last.root], frame: [first.frame, last.frame], content: [first.content, last.content], lift };
    const moves = [...motion.root, ...motion.frame, ...motion.content, lift].some((value) => Math.abs(value) > PAGE_PANE_WINDOW_TOLERANCE_PX);
    return moves ? motion : null;
};

export { collapsePagePaneSpan, resolvePagePaneAnchor, resolvePagePaneLayerMotion, toPagePaneSpan };
export type { PagePaneAnchor, PagePaneLayerMotion, PagePaneSpan };
