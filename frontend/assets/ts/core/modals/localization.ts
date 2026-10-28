/* SoAI - State-preserving localization of explicitly owned modal presentation [frontend/assets/ts/core/modals/localization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAttributeValue } from '@core/dom/patching.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { dom } from '@core/dom/dom.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';

interface ModalLocalizationSlot {
    element: HTMLElement;
    fields: readonly string[];
    textNodes: readonly Text[];
}

const readModalLocalizationSlots = (root: HTMLElement): readonly ModalLocalizationSlot[] => {
    return dom
        .resolveAll('[data-modal-localize], [data-modal-localize-label]', root)
        .filter((element) => !element.parentElement?.closest('[data-modal-localize~="content"]'))
        .map((element) => {
            if (!(element instanceof HTMLElement)) throw new Error('Modal localization requires an HTMLElement');
            const fields = (element.getAttribute('data-modal-localize') ?? '').split(/\s+/).filter(Boolean);
            if (element.hasAttribute('data-modal-localize-label')) fields.push('aria-label', 'data-tooltip');
            if (fields.length === 0 || fields.some((field) => !['text', 'content', 'options', 'aria-label', 'data-tooltip', 'placeholder', 'title', 'data-toggle-label-true', 'data-toggle-label-false'].includes(field))) {
                throw new Error('Invalid modal localization fields');
            }
            return { element, fields, textNodes: directTextNodes(element) };
        });
};

const directTextNodes = (element: HTMLElement): readonly Text[] => Array.from(element.childNodes).filter((node): node is Text => node instanceof Text);

const prepareModalLocalization = (root: HTMLElement): ((source: HTMLElement) => void) => {
    const targets = readModalLocalizationSlots(root);
    return (source): void => {
        const sources = readModalLocalizationSlots(source);
        if (targets.length !== sources.length) throw new Error(`Modal "${root.id}" localization shape changed`);
        const changes: Array<() => void> = [];
        targets.forEach((target, index) => {
            const replacement = sources[index];
            if (!replacement || target.element.tagName !== replacement.element.tagName || target.fields.join(' ') !== replacement.fields.join(' ')) {
                throw new Error(`Modal "${root.id}" localization slot changed`);
            }
            if (!root.contains(target.element) || target.element.closest('[data-modal-localization-owner="session"]')) return;
            for (const field of target.fields) {
                if (field === 'options') {
                    if (!(target.element instanceof HTMLSelectElement) || !(replacement.element instanceof HTMLSelectElement)) throw new Error('Modal option localization requires select elements');
                    const labels = new Map(Array.from(replacement.element.options, (option) => [option.value, option.text]));
                    for (const option of target.element.options) {
                        const label = labels.get(option.value);
                        if (label !== undefined)
                            changes.push(() => {
                                if (option.text !== label) option.text = label;
                            });
                    }
                } else if (field === 'content') {
                    changes.push(() => reconcileChildNodes(target.element, Array.from(replacement.element.childNodes)));
                } else if (field === 'text') {
                    if (directTextNodes(replacement.element).length === 0) continue;
                    const targetNodes = target.textNodes;
                    const sourceNodes = directTextNodes(replacement.element);
                    if (targetNodes.length !== sourceNodes.length) throw new Error(`Modal "${root.id}" localization text shape changed`);
                    targetNodes.forEach((node, textIndex) => {
                        const value = sourceNodes[textIndex]?.data ?? '';
                        changes.push(() => {
                            if (node.parentNode === target.element && node.data !== value) node.data = value;
                        });
                    });
                } else {
                    const value = replacement.element.getAttribute(field);
                    changes.push(() => {
                        if (field === 'data-tooltip') setTooltipText(target.element, value);
                        else syncAttributeValue(target.element, field, value);
                    });
                }
            }
        });
        for (const change of changes) change();
        for (const input of dom.resolveAll('.toggle-switch input', root)) {
            if (input instanceof HTMLInputElement) updateToggleLabel(input);
        }
        dom.flush();
    };
};

export { prepareModalLocalization };
