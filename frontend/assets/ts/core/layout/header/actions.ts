/* SoAI - Shared layout header actions [frontend/assets/ts/core/layout/header/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { HeaderActionEvent, HEADER_ACTION_EVENTS } from '@core/headerActionBus.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { GlobalPresentationOwner } from '@core/routing/router/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const defineHeaderActions = (owner: GlobalPresentationOwner): void => {
    const define = (id: string, icon: IconName, order: number, label: string, cls: string, tooltip: string = label, ariaLabel: string = label): void => {
        getHeaderActions().defineAction(id, owner, {
            id,
            icon,
            order,
            label,
            tooltip,
            ariaLabel,
            className: cls
        });
    };
    define(HEADER_ACTION_IDS.scrollToTop, 'chevron-up', 10, i18n.t('header.actions.scrollToTop'), 'header-action--scroll');
    define(HEADER_ACTION_IDS.save, 'save', 20, i18n.t('header.actions.save'), 'header-action--save');
    define(HEADER_ACTION_IDS.edit, 'edit', 20, i18n.t('header.actions.edit'), 'header-action--edit ui-variant-neutral');
    define(HEADER_ACTION_IDS.licensing, 'key', 25, i18n.t('header.actions.openLicensing'), 'header-action--licensing ui-variant-danger');
    define(HEADER_ACTION_IDS.restartReminder, 'restart', 30, i18n.t('header.restartReminder.indicator'), 'header-action--restart ui-variant-warning', i18n.t('header.restartReminder.tooltip'));
    define(HEADER_ACTION_IDS.detach, 'window', 40, i18n.t('header.actions.detach'), 'header-action--detach');
};

interface HeaderActionBridgeHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getEventHubTarget: () => EventTarget;
}

const bindHeaderActionEventBridge = (host: HeaderActionBridgeHost): (() => void)[] => {
    const eventHub = host.getEventHubTarget();
    const disposers: (() => void)[] = [];
    const add = (eventName: string, functionValue: (event: Event) => void): void => {
        const disposer = host.on(eventHub, eventName, functionValue);
        if (typeof disposer === 'function') disposers.push(disposer);
    };

    add(HEADER_ACTION_EVENTS.define, (event) => {
        if (!(event instanceof HeaderActionEvent) || event.detail.type !== 'define') return;
        const { actionId, owner, definition } = event.detail;
        getHeaderActions().defineAction(actionId, owner, definition);
    });
    add(HEADER_ACTION_EVENTS.update, (event) => {
        if (!(event instanceof HeaderActionEvent) || event.detail.type !== 'update') return;
        const { actionId, contextId, registration, state } = event.detail;
        getHeaderActions().setActionState(actionId, contextId, registration, state);
    });
    add(HEADER_ACTION_EVENTS.remove, (event) => {
        if (!(event instanceof HeaderActionEvent) || event.detail.type !== 'remove') return;
        const { actionId, contextId, registration } = event.detail;
        getHeaderActions().removeActionContext(actionId, contextId, registration);
    });

    return disposers;
};

const disposeHeaderActionEventBridge = (disposers: (() => void)[]): void => {
    for (const entry of disposers) {
        try {
            entry();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('HeaderActionBridge', 'Disposer failed', runtimeError);
        }
    }
};

export { defineHeaderActions, bindHeaderActionEventBridge, disposeHeaderActionEventBridge };
