/* SoAI - Hardware card row reconciliation [frontend/assets/ts/pages/hardware/rendering/cards/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';

const reconcileHardwareRows = <Model>(container: Element, rowSelector: string, models: Model[], resolveKey: (model: Model) => string, createRow: (model: Model, index: number) => HTMLElement): void => {
    const previousRows = new Map(
        dom
            .resolveAll(rowSelector, container)
            .filter((row): row is HTMLElement => row instanceof HTMLElement)
            .map((row) => [row.dataset['hardwareRowKey'], row])
    );
    const previousOrder = [...previousRows.keys()];
    models.sort((first, second) => {
        const firstIndex = previousOrder.indexOf(resolveKey(first));
        const secondIndex = previousOrder.indexOf(resolveKey(second));
        return (firstIndex < 0 ? previousOrder.length : firstIndex) - (secondIndex < 0 ? previousOrder.length : secondIndex);
    });
    const nodes = models.map((model, index) => {
        const key = resolveKey(model);
        const next = createRow(model, index);
        const existing = previousRows.get(key);
        if (existing) {
            existing.className = next.className;
            reconcileChildNodes(existing, Array.from(next.childNodes));
            return existing;
        }
        next.dataset['hardwareRowKey'] = key;
        return next;
    });
    for (const child of Array.from(container.children)) {
        if (child instanceof HTMLElement && !nodes.includes(child)) removeWithPresence(child);
    }
    nodes.forEach((node, index) => {
        const reference = container.children.item(index);
        insertWithPresence(container, node, reference);
        if (reference !== node) container.insertBefore(node, reference);
    });
};

export { reconcileHardwareRows };
