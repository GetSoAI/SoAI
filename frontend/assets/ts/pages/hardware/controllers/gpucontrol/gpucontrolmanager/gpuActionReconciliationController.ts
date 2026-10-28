/* SoAI - GPU action reconciliation preserving presence motion across panel updates [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuActionReconciliationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceContentWithFade } from '@core/animations/contentReplacement.ts';
import { insertWithPresence, isPresenceExiting, removeWithPresence } from '@core/animations/presence/public.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { dom } from '@core/dom/dom.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { preserveGpuValueEditors } from '@pages/hardware/controllers/gpucontrol/gpuControlValueEditorController.ts';

const patchGpuFooter = (target: HTMLElement, source: HTMLElement): void => {
    const displayedContent = target.dataset['content'] ?? 'telemetry';
    const requestedContent = source.dataset['content'] ?? 'telemetry';
    const showContent = (content: string): void => {
        const boot = dom.resolve('.gpu-boot-toggle-container', target);
        const telemetry = dom.resolve('.gpu-boot-telemetry', target);
        if (boot instanceof HTMLElement) {
            boot.classList.toggle('gpu-boot-toggle-container--reserved', content !== 'boot');
            boot.setAttribute('aria-hidden', content === 'boot' ? 'false' : 'true');
        }
        if (telemetry instanceof HTMLElement) {
            const visible = content === 'telemetry' && !!telemetry.textContent;
            telemetry.classList.toggle('gpu-boot-telemetry--hidden', !visible);
            telemetry.setAttribute('aria-hidden', visible ? 'false' : 'true');
        }
        target.dataset['content'] = content;
    };
    reconcileChildNodes(target, Array.from(source.childNodes));
    showContent(displayedContent);
    replaceContentWithFade(target, requestedContent, showContent, displayedContent);
};

const PRESERVED_PRESENCE_ATTRIBUTES = new Set(['data-presence-state']);

const resolveActionKey = (element: HTMLElement): string | null => {
    const action = element.dataset['action'];
    if (action) return `${action}:${element.dataset['slotId'] ?? ''}`;
    for (const className of ['gpu-primary-action-group', 'gpu-slot-group', 'gpu-soaibench-actions', 'gpu-soaibench-state']) {
        if (element.classList.contains(className)) return className;
    }
    return null;
};

const patchGpuPrimaryActionGroup = (target: HTMLElement, source: HTMLElement): void => {
    const desiredKeys = new Set(Array.from(source.children).flatMap((child) => (child instanceof HTMLElement ? [resolveActionKey(child)] : [])));
    for (const child of Array.from(target.children)) {
        if (child instanceof HTMLElement && isPresenceExiting(child) && desiredKeys.has(resolveActionKey(child))) insertWithPresence(target, child);
    }
    patchOrderedChildren({
        existingParent: target,
        createdParent: source,
        resolveChildKey: resolveActionKey,
        insertChild(parent, child, anchor): HTMLElement {
            insertWithPresence(parent, child, anchor);
            return child;
        },
        patchChild(existing, created): boolean {
            const changed = syncElementShell({ target: existing, source: created, preservedAttributeNames: PRESERVED_PRESENCE_ATTRIBUTES });
            if (existing.matches('.gpu-primary-action-group, .gpu-slot-group, .gpu-soaibench-actions')) {
                patchGpuPrimaryActionGroup(existing, created);
            } else if (!existing.isEqualNode(created)) {
                reconcileChildNodes(existing, Array.from(created.childNodes));
                return true;
            }
            return changed;
        },
        removeChild: removeWithPresence,
        replaceUnsupportedChildren(): boolean {
            throw new Error('GPU primary actions require unique action identities');
        },
        isChildDetaching: isPresenceExiting
    });
};

const patchGpuControlPanel = (existing: HTMLElement, created: HTMLElement): void => {
    preserveGpuValueEditors(existing, created);
    const actions = dom.resolve('.gpu-primary-actions', existing);
    const nextActions = dom.resolve('.gpu-primary-actions', created);
    if (!(actions instanceof HTMLElement) || !(nextActions instanceof HTMLElement)) throw new Error('GPU primary actions are required');
    const footer = dom.resolve('.gpu-boot-toggle-row', existing);
    const nextFooter = dom.resolve('.gpu-boot-toggle-row', created);
    if (!(footer instanceof HTMLElement) || !(nextFooter instanceof HTMLElement)) throw new Error('GPU footer is required');
    nextActions.replaceWith(actions.cloneNode(true));
    nextFooter.replaceWith(footer.cloneNode(true));
    syncElementShell({ target: existing, source: created });
    reconcileChildNodes(existing, Array.from(created.childNodes));
    patchGpuPrimaryActionGroup(actions, nextActions);
    patchGpuFooter(footer, nextFooter);
};

const reconcileGpuControlPanels = (container: HTMLElement, markup: string): void => {
    const created = container.ownerDocument.createElement('div');
    created.appendChild(createHtmlFragment({ documentRef: container.ownerDocument, html: markup, context: container }));
    patchOrderedChildren({
        existingParent: container,
        createdParent: created,
        resolveChildKey: (panel) => panel.dataset['gpuIndex'] ?? null,
        insertChild(parent, panel, anchor): HTMLElement {
            parent.insertBefore(panel, anchor);
            return panel;
        },
        patchChild(existing, next): boolean {
            patchGpuControlPanel(existing, next);
            return true;
        },
        removeChild: (panel) => panel.remove(),
        replaceUnsupportedChildren(): boolean {
            container.replaceChildren(...Array.from(created.childNodes));
            return true;
        }
    });
};

export { patchGpuPrimaryActionGroup, reconcileGpuControlPanels, patchGpuControlPanel };
