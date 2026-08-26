/* SoAI - Frontend application lifecycle DOM event ownership [frontend/assets/ts/app/bootstrap/stages/applifecycle/lifecycleDomEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskManagerApi } from '@app/bootstrap/stages/applifecycle/types.ts';
import { SETUP_REQUIRED_AUTH_EVENT } from '@core/auth/sessionFailure.ts';
import { dom } from '@core/dom/dom.ts';
import { getElementByIdStrict, getEventHub, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { StateManager } from '@core/state/public.ts';
import { isInstanceOf, isString } from '@core/typeGuards.ts';

interface SetupLifecycleEventListenersOptions {
    tracker: ResourceTracker;
    taskManager: TaskManagerApi;
    state: StateManager;
    recoverFreshInstallSession: () => Promise<boolean>;
}

const setupLifecycleEventListeners = ({ tracker, taskManager, state, recoverFreshInstallSession }: SetupLifecycleEventListenersOptions): void => {
    tracker.addEventListener(window, 'beforeunload', (event) => {
        if (!(event instanceof BeforeUnloadEvent)) return;
        const actions = getHeaderActions().snapshot.actions;
        const hasUnsaved = actions.find((action) => action.id === 'save')?.visible === true;
        if (!hasUnsaved) return;
        const warning = i18n.t('settings.unsavedChanges');
        event.preventDefault();
        event.returnValue = warning;
    });

    const documentRef = requireDocument();
    tracker.addEventListener(documentRef, 'visibilitychange', () => {
        if (documentRef.hidden) taskManager.collapse();
    });
    tracker.addEventListener(documentRef, 'click', (event) => {
        const target = event.target;
        if (!isInstanceOf(target, Element)) return;
        const toggle = target.closest('[data-toggle]');
        if (!toggle) return;
        const id = dom.getData(toggle, 'toggle');
        if (!isString(id) || !id) return;
        const section = getElementByIdStrict(id);
        const isVisible = !dom.hasClass(section, 'u-hidden') && section.offsetParent !== null;
        state.toggleHidden(section, isVisible);
        dom.setStyle(section, 'display', isVisible ? 'none' : '');
        dom.toggleClass(toggle, 'is-active', !isVisible);
    });
    tracker.addEventListener(getEventHub(), SETUP_REQUIRED_AUTH_EVENT, () => {
        void recoverFreshInstallSession().catch((error) => {
            errorHandler.warn('AppLifecycle', 'Fresh install recovery from setup-required event failed', ensureError(error));
        });
    });
};

export { setupLifecycleEventListeners };
