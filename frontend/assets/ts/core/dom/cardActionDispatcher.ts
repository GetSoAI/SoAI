/* SoAI - Shared DOM card action dispatcher [frontend/assets/ts/core/dom/cardActionDispatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement } from '@core/dom/attributes.ts';
import type { TypedResolvedActionEvent } from '@core/dom/dataActionBinding.ts';

interface CardActionDispatchEvent<TAction extends string, TItem> extends TypedResolvedActionEvent<TAction> {
    card: HTMLElement;
    item: TItem;
}

interface CardActionDispatcherOptions<TAction extends string, TItem> {
    cardSelector: string;
    context: string;
    resolveItem: (card: HTMLElement, actionEvent: TypedResolvedActionEvent<TAction>) => TItem | null;
    onAction: (actionEvent: CardActionDispatchEvent<TAction, TItem>) => void | Promise<void>;
}

const requireActionCard = (element: Element, selector: string, context: string): HTMLElement => {
    const card = requireClosestElement(element, selector, context);
    if (!(card instanceof HTMLElement)) {
        throw new Error(`${context} requires an HTMLElement card`);
    }
    return card;
};

const createCardActionDispatcher = <TAction extends string, TItem>(options: CardActionDispatcherOptions<TAction, TItem>): ((actionEvent: TypedResolvedActionEvent<TAction>) => void | Promise<void>) => {
    return (actionEvent: TypedResolvedActionEvent<TAction>): void | Promise<void> => {
        const card = requireActionCard(actionEvent.actionElement, options.cardSelector, options.context);
        const item = options.resolveItem(card, actionEvent);
        if (item === null) {
            throw new Error(`${options.context} requires a resolved card item`);
        }
        return options.onAction({
            event: actionEvent.event,
            action: actionEvent.action,
            actionElement: actionEvent.actionElement,
            card,
            item
        });
    };
};

export { createCardActionDispatcher };
export type { CardActionDispatchEvent, CardActionDispatcherOptions };
