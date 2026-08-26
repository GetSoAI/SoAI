/* SoAI - Models page root event controller [frontend/assets/ts/pages/models/controllers/page/modelsRootEventController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { isModelsDataActionId, type ModelsDataActionId } from '@pages/models/actions.ts';

type ModelsRootClickHandler = (event: Event, action: ModelsDataActionId, actionElement?: HTMLElement | null) => void;

const bindModelsRootEventListeners = (signal: AbortSignal, root: HTMLElement, rootClickHandler: ModelsRootClickHandler): void => {
    bindPageActionDispatcher({
        label: 'ModelsPage',
        root,
        signal,
        isAction: isModelsDataActionId,
        events: {
            click: {
                mouseButton: 'primary',
                preventDefault: 'never',
                ignorePrevented: true,
                onAction: ({ event, action, actionElement }): void => {
                    if (!(event instanceof MouseEvent)) {
                        return;
                    }
                    rootClickHandler(event, action, actionElement);
                }
            }
        }
    });
};

export { bindModelsRootEventListeners };
