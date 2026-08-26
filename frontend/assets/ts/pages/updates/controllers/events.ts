/* SoAI - Updates page controllers events [frontend/assets/ts/pages/updates/controllers/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton } from '@core/dom/narrowElement.ts';
import { isUpdatesActionId, UPDATES_ACTION_CHECK, UPDATES_ACTION_INSTALL } from '@pages/updates/actions.ts';

interface UpdatesPageActionHandlers {
    onCheckUpdates: () => Promise<void> | void;
    onInstallSystemUpdate: (button: HTMLButtonElement) => Promise<void> | void;
}

interface HandleUpdatesPageClickOptions {
    event: Event;
    actionElement: HTMLElement;
    handlers: UpdatesPageActionHandlers;
}

const handleAction = (action: string, actionElement: HTMLElement, handlers: UpdatesPageActionHandlers): void => {
    const requireButton = (): HTMLButtonElement => {
        return narrowButton(actionElement, `Updates action "${action}"`);
    };
    if (action === UPDATES_ACTION_CHECK) {
        void handlers.onCheckUpdates();
        return;
    }
    if (action === UPDATES_ACTION_INSTALL) {
        void handlers.onInstallSystemUpdate(requireButton());
        return;
    }
};

const handleUpdatesPageClick = (options: HandleUpdatesPageClickOptions): void => {
    const { event, actionElement, handlers } = options;
    const action = actionElement.dataset['action'];
    if (!isUpdatesActionId(action)) {
        return;
    }

    event.preventDefault();
    handleAction(action, actionElement, handlers);
};

export { handleUpdatesPageClick };
export type { UpdatesPageActionHandlers };
