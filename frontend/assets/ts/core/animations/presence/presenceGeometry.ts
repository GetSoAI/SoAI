/* SoAI - Presence motion layout geometry [frontend/assets/ts/core/animations/presence/presenceGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type PresenceAxis = 'inline' | 'block';
type PresenceGapSide = 'start' | 'end' | null;

interface PresenceGeometry {
    axis: PresenceAxis;
    size: number;
    gap: number;
    gapSide: PresenceGapSide;
}

interface PresenceAxisProperties {
    size: 'width' | 'height';
    minSize: 'minWidth' | 'minHeight';
    paddingStart: 'paddingInlineStart' | 'paddingBlockStart';
    paddingEnd: 'paddingInlineEnd' | 'paddingBlockEnd';
    borderStart: 'borderInlineStartWidth' | 'borderBlockStartWidth';
    borderEnd: 'borderInlineEndWidth' | 'borderBlockEndWidth';
    marginStart: 'marginInlineStart' | 'marginBlockStart';
    marginEnd: 'marginInlineEnd' | 'marginBlockEnd';
}

const INLINE_AXIS_PROPERTIES: PresenceAxisProperties = {
    size: 'width',
    minSize: 'minWidth',
    paddingStart: 'paddingInlineStart',
    paddingEnd: 'paddingInlineEnd',
    borderStart: 'borderInlineStartWidth',
    borderEnd: 'borderInlineEndWidth',
    marginStart: 'marginInlineStart',
    marginEnd: 'marginInlineEnd'
};

const BLOCK_AXIS_PROPERTIES: PresenceAxisProperties = {
    size: 'height',
    minSize: 'minHeight',
    paddingStart: 'paddingBlockStart',
    paddingEnd: 'paddingBlockEnd',
    borderStart: 'borderBlockStartWidth',
    borderEnd: 'borderBlockEndWidth',
    marginStart: 'marginBlockStart',
    marginEnd: 'marginBlockEnd'
};

const resolveAxisProperties = (axis: PresenceAxis): PresenceAxisProperties => (axis === 'inline' ? INLINE_AXIS_PROPERTIES : BLOCK_AXIS_PROPERTIES);

const readComputedStyle = (element: Element): CSSStyleDeclaration | null => element.ownerDocument.defaultView?.getComputedStyle(element) ?? null;

const parsePixels = (value: string): number => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

const isRendered = (element: Element): boolean => element.getClientRects().length > 0;
const resolveLayoutParent = (element: Element): Element | null => {
    let parent = element.parentElement;
    while (parent && readComputedStyle(parent)?.display === 'contents') {
        parent = parent.parentElement;
    }
    return parent;
};

const isLayoutParentRendered = (element: Element): boolean => {
    const parent = resolveLayoutParent(element);
    return parent !== null && isRendered(parent);
};

const hasRenderedItem = (items: readonly Element[]): boolean =>
    items.some((item) => {
        if (readComputedStyle(item)?.display === 'contents') {
            return hasRenderedItem(Array.from(item.children));
        }
        return isRendered(item);
    });

const collectSiblings = (element: Element, direction: 'previous' | 'next'): Element[] => {
    const siblings: Element[] = [];
    let node: Element | null = element;
    while (node) {
        let sibling = direction === 'next' ? node.nextElementSibling : node.previousElementSibling;
        while (sibling) {
            siblings.push(sibling);
            sibling = direction === 'next' ? sibling.nextElementSibling : sibling.previousElementSibling;
        }
        const parent: Element | null = node.parentElement;
        node = parent && readComputedStyle(parent)?.display === 'contents' ? parent : null;
    }
    return siblings;
};
const resolveGapSide = (element: Element): PresenceGapSide => {
    if (hasRenderedItem(collectSiblings(element, 'next'))) {
        return 'end';
    }
    if (hasRenderedItem(collectSiblings(element, 'previous'))) {
        return 'start';
    }
    return null;
};

const resolvePresenceAxis = (style: CSSStyleDeclaration, parentStyle: CSSStyleDeclaration | null): PresenceAxis | null => {
    if (style.position === 'absolute' || style.position === 'fixed') {
        return null;
    }
    if (!parentStyle) {
        return null;
    }
    if (parentStyle.display.includes('flex')) {
        return parentStyle.flexDirection.startsWith('column') ? 'block' : 'inline';
    }
    if (parentStyle.display.includes('grid')) {
        return null;
    }
    return style.display.startsWith('inline') ? 'inline' : 'block';
};
const measurePresenceGeometry = (element: HTMLElement): PresenceGeometry | null => {
    const style = readComputedStyle(element);
    if (!style) {
        return null;
    }
    const parent = resolveLayoutParent(element);
    const parentStyle = parent ? readComputedStyle(parent) : null;
    const axis = resolvePresenceAxis(style, parentStyle);
    if (!axis || !parentStyle) {
        return null;
    }
    const rawSize = style[resolveAxisProperties(axis).size];
    if (!rawSize.endsWith('px')) {
        return null;
    }
    const size = parsePixels(rawSize);
    const isFlex = parentStyle.display.includes('flex');
    const gap = isFlex ? parsePixels(axis === 'inline' ? parentStyle.columnGap : parentStyle.rowGap) : 0;
    return { axis, size, gap, gapSide: gap > 0 ? resolveGapSide(element) : null };
};

export { isLayoutParentRendered, isRendered, measurePresenceGeometry, parsePixels, readComputedStyle, resolveAxisProperties };
export type { PresenceAxis, PresenceAxisProperties, PresenceGeometry };
