/* SoAI - Shared page outlet slots [frontend/assets/ts/core/pageoutlet/slots.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isPageOutletSlot = (node: Node): node is Element => node.nodeType === Node.ELEMENT_NODE && node instanceof Element && node.hasAttribute('data-page-outlet-slot');

const resolvePageOutletSlots = (container: HTMLElement): Element[] => Array.from(container.childNodes).filter(isPageOutletSlot);

const removeNonPageOutletSlotNodes = (container: HTMLElement): void => {
    const nodes = Array.from(container.childNodes);
    nodes.forEach((node) => {
        if (isPageOutletSlot(node)) {
            return;
        }
        container.removeChild(node);
    });
};

const restorePageOutletSlots = (container: HTMLElement, slots: Element[]): void => {
    for (const slot of slots) {
        if (slot.parentElement !== container) {
            container.append(slot);
        }
    }
};

const replaceContentPreservingPageOutletSlots = (container: HTMLElement, replaceContent: () => void): void => {
    const slots = resolvePageOutletSlots(container);
    replaceContent();
    restorePageOutletSlots(container, slots);
};

export { isPageOutletSlot, removeNonPageOutletSlotNodes, replaceContentPreservingPageOutletSlots };
