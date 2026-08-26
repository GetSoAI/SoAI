/* SoAI - Shared routing runtime bindings [frontend/assets/ts/core/routing/pages/movablesections/runtimeBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import type { MovableSectionId, MovableSectionLayoutContext } from '@core/routing/pages/movablesections/types.ts';
import { AutoScroller } from '@core/ui/AutoScroller.ts';
import { GridAnimator } from '@core/ui/GridAnimator.ts';

interface MovableSectionRuntimeBindingTarget<TSectionId extends MovableSectionId> extends MovableSectionLayoutContext<TSectionId> {
    responsiveDisposers: Array<() => void>;
    initializeResponsiveLayout: () => void;
    toggleGridMode: (collapsed: boolean) => void;
    updateResponsiveLayout: () => void;
    cancelDrag: () => void;
}

const resetMovableSectionRuntimeBindings = <TSectionId extends MovableSectionId>(target: MovableSectionRuntimeBindingTarget<TSectionId>): void => {
    target.cancelDrag();
    disposeMovableSectionBindings(target);
    for (const dispose of target.responsiveDisposers) {
        dispose();
    }
    target.responsiveDisposers = [];
    target.gridAnimator?.destroy();
    target.gridAnimator = null;
    target.autoScroller?.destroy();
    target.autoScroller = null;
    target.gridElement = null;
    target.metrics = null;
};

const disposeMovableSectionBindings = <TSectionId extends MovableSectionId>(target: MovableSectionRuntimeBindingTarget<TSectionId>): void => {
    for (const dispose of target.sectionDisposers) {
        try {
            dispose();
        } catch (error) {
            const runtimeError = ensureError(error);
            target.host.logger('debug', target.config.logLabel, { name: runtimeError.name, message: runtimeError.message });
        }
    }
    target.sectionDisposers = [];
};

const initializeMovableSectionRuntimeBindings = <TSectionId extends MovableSectionId>(target: MovableSectionRuntimeBindingTarget<TSectionId>): void => {
    resetMovableSectionRuntimeBindings(target);
    target.gridElement = target.host.requireHTMLElement(target.config.gridSelector);
    target.initializeResponsiveLayout();
    const windowRef = target.gridElement.ownerDocument.defaultView;
    if (!windowRef) throw new Error('Movable grid requires a document window');
    const responsiveHandler = (): void => target.updateResponsiveLayout();
    target.responsiveDisposers.push(target.host.on(windowRef, 'resize', responsiveHandler));
    target.responsiveDisposers.push(target.host.on(windowRef, INTERFACE_SCALE_CHANGED_EVENT, responsiveHandler));
    target.gridAnimator = new GridAnimator({
        gridElement: target.gridElement,
        getSections: (container: HTMLElement): HTMLElement[] => {
            return Array.from(dom.resolveAll(target.config.sectionSelector, container)).filter((section: Element): section is HTMLElement => section instanceof HTMLElement);
        },
        getSectionId: (section: HTMLElement): string | null => resolveMovableSectionElementId(target, section)
    });
    target.autoScroller = new AutoScroller({ scrollContainer: target.host.optionalUI('.page-scrollable') });
};

const resolveMovableSectionElementId = <TSectionId extends MovableSectionId>(target: MovableSectionRuntimeBindingTarget<TSectionId>, section: HTMLElement): string | null => {
    const sectionId = section.getAttribute(target.config.sectionIdAttribute);
    return sectionId && target.config.isSectionId(sectionId) ? sectionId : null;
};

export { disposeMovableSectionBindings, initializeMovableSectionRuntimeBindings, resetMovableSectionRuntimeBindings };
export type { MovableSectionRuntimeBindingTarget };
