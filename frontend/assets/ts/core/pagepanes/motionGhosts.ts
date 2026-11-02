/* SoAI - Static replicas of pane items that cross-fade the previous layout into the next one [frontend/assets/ts/core/pagepanes/motionGhosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { captureScrollState, dom } from '@core/dom/dom.ts';
import { setSelectSelectedIndexAndSyncDefault, syncSelectDefaultSelectedToCurrent } from '@core/dom/selectSelection.ts';
import { getCspNonce } from '@core/security/cspNonce.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { isPagePaneItemResized, measurePagePaneItemOrigin, resolvePagePaneSection, type PagePaneItemPositions } from '@core/pagepanes/motionContent.ts';
import type { PagePaneGhostLayer, PagePaneTransition } from '@core/pagepanes/motionStage.ts';

const PAGE_PANE_GHOST_LAYER_CLASS = 'page-pane-ghost-layer';
const PAGE_PANE_GHOST_NODE_CLASS = 'page-pane-ghost-node';
const PAGE_PANE_GHOST_FRAME_CLASS = 'page-pane-ghost-frame';
const PAGE_PANE_GHOST_CONTAINER = 'ui-viewport';
const PAGE_PANE_GHOST_FADE_END = 0.6;

interface PagePaneGhostFrame {
    readonly element: HTMLElement;
    readonly box: GeometryBox;
}

const resolvePagePaneGhostFrame = (element: HTMLElement): GeometryBox => {
    const box = measureLayoutBox(element);
    const style = getComputedStyleStrict(element);
    const left = box.left + Number.parseFloat(style.borderLeftWidth);
    const top = box.top + Number.parseFloat(style.borderTopWidth);
    return { ...box, left, top };
};

const PAGE_PANE_GHOST_REFERENCE_PATTERN = /(url\(\s*['"]?#|^#)([^'")\s]+)/g;

let pagePaneGhostSequence = 0;

const renamePagePaneGhostIds = (ghost: HTMLElement): ReadonlyMap<string, string> => {
    const renamed = new Map<string, string>();
    for (const element of [ghost, ...dom.resolveAll('[id]', ghost)]) {
        if (!element.id) continue;
        pagePaneGhostSequence += 1;
        renamed.set(element.id, `${element.id}--page-pane-ghost-${String(pagePaneGhostSequence)}`);
        element.id = renamed.get(element.id) ?? '';
    }
    if (renamed.size === 0) return renamed;
    for (const element of [ghost, ...dom.resolveAll('*', ghost)]) {
        for (const attribute of Array.from(element.attributes)) {
            if (['for', 'form', 'list', 'headers', 'aria-labelledby', 'aria-describedby', 'aria-controls', 'aria-owns', 'aria-activedescendant', 'aria-details', 'aria-errormessage', 'aria-flowto'].includes(attribute.name)) {
                element.setAttribute(
                    attribute.name,
                    attribute.value
                        .split(/\s+/u)
                        .map((id) => renamed.get(id) ?? id)
                        .join(' ')
                );
                continue;
            }
            if (!['href', 'xlink:href', 'clip-path', 'mask', 'filter', 'fill', 'stroke', 'marker-start', 'marker-mid', 'marker-end'].includes(attribute.name) || !attribute.value.includes('#')) continue;
            const value = attribute.value.replace(PAGE_PANE_GHOST_REFERENCE_PATTERN, (match: string, prefix: string, id: string) => {
                const next = renamed.get(id);
                return next === undefined ? match : `${prefix}${next}`;
            });
            if (value !== attribute.value) element.setAttribute(attribute.name, value);
        }
    }
    return renamed;
};

const placePagePaneGhost = (ghost: HTMLElement, box: GeometryBox, frame: GeometryBox): void => {
    ghost.classList.add(PAGE_PANE_GHOST_NODE_CLASS);
    dom.setStyles(ghost, {
        '--page-pane-ghost-left': `${String(box.left - frame.left)}px`,
        '--page-pane-ghost-top': `${String(box.top - frame.top)}px`,
        '--page-pane-ghost-width': `${String(box.width)}px`,
        '--page-pane-ghost-height': `${String(box.height)}px`
    });
};

const clonePagePaneGhost = (element: HTMLElement, deep: boolean): HTMLElement | null => {
    const ghost = element.cloneNode(deep);
    if (!(ghost instanceof HTMLElement)) return null;
    const originals = [element, ...dom.resolveAll('[style], style', element)];
    for (const [index, copy] of [ghost, ...dom.resolveAll('[style], style', ghost)].entries()) {
        if (copy instanceof HTMLStyleElement) copy.nonce = getCspNonce({ document: copy.ownerDocument }) ?? '';
        if (!(copy instanceof HTMLElement || copy instanceof SVGElement) || !copy.hasAttribute('style')) continue;
        const original = originals[index];
        if (!original) throw new Error('Replica inline styles lost their source');
        const styles = Object.fromEntries(Array.from(copy.style).map((property) => [property, `${copy.style.getPropertyValue(property) || getComputedStyleStrict(original).getPropertyValue(property)}${copy.style.getPropertyPriority(property) ? ' !important' : ''}`]));
        copy.removeAttribute('style');
        dom.setStyles(copy, styles);
    }
    for (const radio of dom.resolveAll('input[type=radio]', ghost)) radio.removeAttribute('name');
    if (ghost instanceof HTMLInputElement && ghost.type === 'radio') ghost.removeAttribute('name');
    if (!deep) ghost.removeAttribute('id');
    return ghost;
};

const preparePagePaneGhostState = (layer: HTMLElement, ghosts: ReadonlyMap<HTMLElement, HTMLElement>, renamed: ReadonlyMap<string, string>, resources: PagePaneTransition['resources']): (() => void) => {
    const snapshots = Array.from(ghosts).flatMap(([source, ghost]) => {
        const copies = [ghost, ...dom.resolveAll('*', ghost)];
        return [source, ...dom.resolveAll('*', source)].flatMap((original, index) => {
            const copy = copies[index];
            if (copy === undefined) return [];
            const style = getComputedStyleStrict(original);
            const references = Object.fromEntries(
                ['clip-path', '-webkit-clip-path', 'filter', 'mask-image', 'fill', 'stroke', 'marker-start', 'marker-mid', 'marker-end'].flatMap((property) => {
                    const value = style.getPropertyValue(property);
                    const rewritten = value.replace(PAGE_PANE_GHOST_REFERENCE_PATTERN, (match: string, prefix: string, id: string) => {
                        const next = renamed.get(id);
                        return next === undefined ? match : `${prefix}${next}`;
                    });
                    return rewritten === value ? [] : [[property, rewritten]];
                })
            );
            const value = (original instanceof HTMLInputElement && original.type !== 'file') || original instanceof HTMLTextAreaElement ? original.value : null;
            const checked = original instanceof HTMLInputElement ? { checked: original.checked, indeterminate: original.indeterminate } : null;
            const selected = original instanceof HTMLSelectElement ? Array.from(original.options, (option) => option.selected) : null;
            return [{ original, copy, value, checked, selected, references, scroll: original instanceof HTMLElement ? captureScrollState(original) : [] }];
        });
    });
    const styles = layer.ownerDocument.createElement('style');
    styles.nonce = getCspNonce({ document: layer.ownerDocument }) ?? '';
    pagePaneGhostSequence += 1;
    const scope = String(pagePaneGhostSequence);
    layer.setAttribute('data-page-pane-ghost-scope', scope);
    if (snapshots.some((snapshot) => Object.keys(snapshot.references).length > 0)) {
        resources.track(() => styles.remove());
        layer.append(styles);
    }
    return () => {
        for (const [index, { original, copy, value, checked, selected, references, scroll }] of snapshots.entries()) {
            if (Object.keys(references).length > 0) {
                const sheet = styles.sheet;
                if (!sheet) throw new Error('Replica references require their mounted stylesheet');
                copy.setAttribute('data-page-pane-ghost-reference', String(index));
                const ruleIndex = sheet.insertRule(`[data-page-pane-ghost-scope="${scope}"] [data-page-pane-ghost-reference="${String(index)}"] {}`, sheet.cssRules.length);
                const rule = sheet.cssRules.item(ruleIndex);
                if (!(rule instanceof CSSStyleRule)) throw new Error('Replica references require a declaration rule');
                for (const [property, reference] of Object.entries(references)) rule.style.setProperty(property, reference, 'important');
            }
            const position = scroll[0];
            if (position !== undefined) copy.scrollTo({ left: position.left, top: position.top, behavior: 'instant' });
            if (value !== null && (copy instanceof HTMLInputElement || copy instanceof HTMLTextAreaElement)) copy.value = value;
            if (checked && copy instanceof HTMLInputElement) {
                copy.checked = checked.checked;
                copy.indeterminate = checked.indeterminate;
            }
            if (selected && copy instanceof HTMLSelectElement) {
                if (!copy.multiple) setSelectSelectedIndexAndSyncDefault(copy, selected.indexOf(true));
                else {
                    for (const [index, option] of Array.from(copy.options).entries()) option.selected = selected[index] === true;
                    syncSelectDefaultSelectedToCurrent(copy);
                }
            }
            if (!(original instanceof HTMLCanvasElement) || !(copy instanceof HTMLCanvasElement) || original.width === 0 || original.height === 0) continue;
            copy.width = original.width;
            copy.height = original.height;
            copy.getContext('2d')?.drawImage(original, 0, 0);
        }
    };
};

const measurePagePaneGhostContainer = (section: HTMLElement): number => {
    for (let ancestor = section.parentElement; ancestor !== null; ancestor = ancestor.parentElement) {
        const style = getComputedStyleStrict(ancestor);
        if (style.containerName.split(' ').includes(PAGE_PANE_GHOST_CONTAINER)) return measureLayoutBox(ancestor).width - Number.parseFloat(style.paddingLeft) - Number.parseFloat(style.paddingRight) - Number.parseFloat(style.borderLeftWidth) - Number.parseFloat(style.borderRightWidth);
    }
    return measureLayoutBox(section).width;
};

const resolvePagePaneGhostParent = (element: HTMLElement, section: HTMLElement, nodes: Map<HTMLElement, PagePaneGhostFrame>): PagePaneGhostFrame | null => {
    const parent = element.parentElement;
    if (parent === null) return null;
    const existing = nodes.get(parent);
    if (existing !== undefined) return existing;
    const ancestor = resolvePagePaneGhostParent(parent, section, nodes);
    const ghost = ancestor === null ? null : clonePagePaneGhost(parent, false);
    if (ancestor === null || ghost === null) return null;
    const contents = getComputedStyleStrict(parent).display === 'contents';
    placePagePaneGhost(ghost, contents ? ancestor.box : measureLayoutBox(parent), ancestor.box);
    ghost.classList.add(PAGE_PANE_GHOST_FRAME_CLASS);
    ancestor.element.append(ghost);
    const frame = { element: ghost, box: contents ? ancestor.box : resolvePagePaneGhostFrame(parent) };
    nodes.set(parent, frame);
    return frame;
};

const settlePagePaneGhostAnimations = (layer: HTMLElement): void => {
    for (const animation of layer.getAnimations({ subtree: true })) {
        if (Number.isFinite(animation.effect?.getComputedTiming().endTime ?? Infinity)) animation.finish();
    }
};

const isPagePaneItemOnScreen = (item: HTMLElement, viewport: GeometryBox): boolean => {
    const box = measureLayoutBox(item);
    return box.right > viewport.left && box.left < viewport.right && box.bottom > viewport.top && box.top < viewport.bottom;
};

const stagePagePaneGhostRoot = (transition: PagePaneTransition, root: HTMLElement, items: PagePaneItemPositions): void => {
    const section = resolvePagePaneSection(root);
    const outlet = section?.parentElement ?? null;
    const sectionGhost = section === null ? null : clonePagePaneGhost(section, false);
    if (section === null || outlet === null || sectionGhost === null) return;
    const viewport = measureLayoutBox(section);
    const visible = Array.from(items.keys()).filter((item) => isPagePaneItemOnScreen(item, viewport));
    if (visible.length === 0) return;
    const outletFrame = resolvePagePaneGhostFrame(outlet);
    const origin = measurePagePaneItemOrigin(section);
    const layer: PagePaneGhostLayer = { element: outlet.ownerDocument.createElement('div'), root, left: origin.left - outletFrame.left, top: origin.top - outletFrame.top, ghosts: new Map() };
    layer.element.className = PAGE_PANE_GHOST_LAYER_CLASS;
    layer.element.inert = true;
    layer.element.setAttribute('data-presence-suspended', '');
    layer.element.setAttribute('aria-hidden', 'true');
    dom.setStyles(layer.element, { '--page-pane-ghost-width': `${String(measurePagePaneGhostContainer(section))}px`, '--page-pane-ghost-height': `${String(outletFrame.height)}px` });
    sectionGhost.removeAttribute('data-section');
    sectionGhost.dataset['pageScope'] = section.dataset['section'] ?? '';
    placePagePaneGhost(sectionGhost, viewport, outletFrame);
    layer.element.append(sectionGhost);
    const nodes = new Map<HTMLElement, PagePaneGhostFrame>([[section, { element: sectionGhost, box: viewport }]]);
    for (const item of visible) {
        const parent = resolvePagePaneGhostParent(item, section, nodes);
        const ghost = clonePagePaneGhost(item, true);
        if (parent === null || ghost === null) continue;
        placePagePaneGhost(ghost, measureLayoutBox(item), parent.box);
        parent.element.append(ghost);
        layer.ghosts.set(item, ghost);
    }
    const renamed = renamePagePaneGhostIds(layer.element);
    const copyState = preparePagePaneGhostState(layer.element, layer.ghosts, renamed, transition.resources);
    for (const frame of dom.resolveAll('[data-presence-morph]', layer.element)) frame.removeAttribute('data-presence-morph');
    transition.ghostLayers.push(layer);
    outlet.append(layer.element);
    copyState();
    settlePagePaneGhostAnimations(layer.element);
};

const stagePagePaneGhosts = (transition: PagePaneTransition, roots: Iterable<HTMLElement>): void => {
    for (const root of roots) {
        const items = transition.items.get(root);
        if (items !== undefined && items.size > 0) stagePagePaneGhostRoot(transition, root, items);
    }
};

const animatePagePaneGhostLayer = (transition: PagePaneTransition, layer: PagePaneGhostLayer, target: PagePaneItemPositions | undefined, timing: KeyframeAnimationOptions): Animation | null => {
    const origin = transition.items.get(layer.root);
    const section = resolvePagePaneSection(layer.root);
    const outlet = section?.parentElement ?? null;
    if (section === null || outlet === null) return null;
    for (const [item, ghost] of layer.ghosts) {
        const start = origin?.get(item);
        const end = target?.get(item);
        if (start === undefined || end === undefined || !isPagePaneItemResized(start, end)) {
            ghost.remove();
            layer.ghosts.delete(item);
            continue;
        }
        transition.deferred.push(() =>
            ghost.animate(
                [
                    { translate: '0 0', scale: '1 1', transformOrigin: 'left top' },
                    { translate: `${String(end.x - start.x)}px ${String(end.y - start.y)}px`, scale: `${String(end.width / start.width)} ${String(end.height / start.height)}`, transformOrigin: 'left top' }
                ],
                timing
            )
        );
    }
    if (layer.ghosts.size === 0) return null;
    const frame = resolvePagePaneGhostFrame(outlet);
    const current = measurePagePaneItemOrigin(section);
    dom.setStyles(layer.element, { '--page-pane-ghost-shift-x': `${String(current.left - frame.left - layer.left)}px`, '--page-pane-ghost-shift-y': `${String(current.top - frame.top - layer.top)}px` });
    const fade = layer.element.animate(
        [
            { offset: 0, opacity: 1 },
            { offset: PAGE_PANE_GHOST_FADE_END, opacity: 0 },
            { offset: 1, opacity: 0 }
        ],
        timing
    );
    fade.pause();
    return fade;
};

const animatePagePaneGhosts = (transition: PagePaneTransition, targets: ReadonlyMap<HTMLElement, PagePaneItemPositions>, timing: KeyframeAnimationOptions): Animation[] => {
    const animations: Animation[] = [];
    for (const layer of transition.ghostLayers.splice(0)) {
        const fade = animatePagePaneGhostLayer(transition, layer, targets.get(layer.root), timing);
        if (fade === null) {
            layer.element.remove();
            continue;
        }
        transition.ghostLayers.push(layer);
        animations.push(fade);
    }
    return animations;
};

export { animatePagePaneGhosts, stagePagePaneGhosts };
