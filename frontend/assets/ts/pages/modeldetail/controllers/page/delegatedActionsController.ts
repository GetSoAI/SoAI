/* SoAI - Model detail page control layer delegated actions controller [frontend/assets/ts/pages/modeldetail/controllers/page/delegatedActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { ACTION_TOGGLE_MODEL_ENABLED, ACTION_TOGGLE_OPENAI_CAPABILITY, type ActionHandlerMap, type ModeldetailActionId } from '@features/modeldetail/public.ts';

const isToggleAction = (action: ModeldetailActionId): boolean => action === ACTION_TOGGLE_MODEL_ENABLED || action === ACTION_TOGGLE_OPENAI_CAPABILITY;

const dispatchModelDetailDelegatedAction = (dependencies: { event: Event; action: ModeldetailActionId; actionElement: HTMLElement; handlers: ActionHandlerMap }): void => {
    const { event, action, actionElement, handlers } = dependencies;
    const handler = handlers[action];
    if (!handler) {
        throw new Error(`ModelDetail missing action handler for ${action}`);
    }
    if (shouldPreventDefaultForActionElement(actionElement)) {
        event.preventDefault();
    }
    handler(event, actionElement);
};

const handleModelDetailDelegatedClick = (dependencies: { event: Event; action: ModeldetailActionId; actionElement: HTMLElement; handlers: ActionHandlerMap }): void => {
    const { event, action, handlers, actionElement } = dependencies;
    const target = event.target;
    if (target instanceof Element && target.closest('.ui-modal')) {
        return;
    }
    if (isToggleAction(action)) {
        return;
    }
    dispatchModelDetailDelegatedAction({ event, action, actionElement, handlers });
};

const handleModelDetailDelegatedChange = (dependencies: { event: Event; action: ModeldetailActionId; actionElement: HTMLElement; handlers: ActionHandlerMap }): void => {
    const { event, action, handlers, actionElement } = dependencies;
    const target = event.target;
    if (!(target instanceof Element) || target.closest('.ui-modal')) {
        return;
    }
    if (!isToggleAction(action)) {
        return;
    }
    event.stopPropagation();
    dispatchModelDetailDelegatedAction({ event, action, actionElement, handlers });
};

export { dispatchModelDetailDelegatedAction, handleModelDetailDelegatedChange, handleModelDetailDelegatedClick };
