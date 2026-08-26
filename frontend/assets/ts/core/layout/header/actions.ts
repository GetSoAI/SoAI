/* SoAI - Shared layout header actions [frontend/assets/ts/core/layout/header/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { HEADER_ACTION_EVENTS } from '@core/headerActionBus.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { DefinitionInput, PayloadInput } from '@core/headeractions/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

const defineHeaderActions = (): void => {
    const define = (id: string, icon: IconName, order: number, label: string, cls: string, tooltip: string = label, ariaLabel: string = label): void => {
        getHeaderActions().defineAction(id, {
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

interface HeaderActionEventDetail {
    actionId?: JsonValue | null | undefined | undefined;
    contextId?: JsonValue | null | undefined | undefined;
    definition?: JsonValue | null | undefined | undefined;
    state?: JsonValue | null | undefined | undefined;
}

const readDefinitionInput = (value: JsonValue | null | undefined): DefinitionInput => {
    if (!isObject(value)) return {};
    return {
        id: isString(value['id']) ? value['id'] : undefined,
        order: isFiniteNumber(value['order']) ? value['order'] : undefined,
        priority: isFiniteNumber(value['priority']) ? value['priority'] : undefined,
        icon: isString(value['icon']) ? value['icon'] : undefined,
        label: isString(value['label']) ? value['label'] : undefined,
        tooltip: isString(value['tooltip']) ? value['tooltip'] : undefined,
        ariaLabel: isString(value['ariaLabel']) ? value['ariaLabel'] : undefined,
        className: isString(value['className']) ? value['className'] : undefined,
        persistent: isBoolean(value['persistent']) ? value['persistent'] : undefined,
        disabled: isBoolean(value['disabled']) ? value['disabled'] : undefined,
        badge: isString(value['badge']) ? value['badge'] : undefined,
        analyticsId: isString(value['analyticsId']) ? value['analyticsId'] : undefined,
        pressed: isBoolean(value['pressed']) ? value['pressed'] : undefined,
        onClick: isFunction(value['onClick']) ? value['onClick'] : undefined
    };
};

const readPayloadInput = (value: JsonValue | null | undefined): PayloadInput | null => {
    if (!isObject(value)) return null;
    return {
        visible: isBoolean(value['visible']) ? value['visible'] : undefined,
        order: isFiniteNumber(value['order']) ? value['order'] : undefined,
        priority: isFiniteNumber(value['priority']) ? value['priority'] : undefined,
        icon: isString(value['icon']) ? value['icon'] : undefined,
        label: isString(value['label']) ? value['label'] : undefined,
        tooltip: isString(value['tooltip']) ? value['tooltip'] : undefined,
        ariaLabel: isString(value['ariaLabel']) ? value['ariaLabel'] : undefined,
        className: isString(value['className']) ? value['className'] : undefined,
        disabled: isBoolean(value['disabled']) ? value['disabled'] : undefined,
        badge: isString(value['badge']) ? value['badge'] : undefined,
        analyticsId: isString(value['analyticsId']) ? value['analyticsId'] : undefined,
        pressed: isBoolean(value['pressed']) ? value['pressed'] : undefined,
        onClick: isFunction(value['onClick']) ? value['onClick'] : undefined
    };
};

const bindHeaderActionEventBridge = (host: HeaderActionBridgeHost): (() => void)[] => {
    const normalizeId = (value: JsonValue | null | undefined): string => (isString(value) ? value.trim() : '');
    const getDetail = (value: Event): HeaderActionEventDetail | undefined => {
        if (!(value instanceof CustomEvent)) return undefined;
        const detailValue = value.detail;
        return isObject(detailValue) ? detailValue : undefined;
    };
    const getActionId = (detail: HeaderActionEventDetail | undefined): string => normalizeId(detail?.actionId);
    const getContextId = (detail: HeaderActionEventDetail | undefined): string => normalizeId(detail?.contextId);

    const eventHub = host.getEventHubTarget();
    const disposers: (() => void)[] = [];
    const add = (eventName: string, functionValue: (event: Event) => void): void => {
        const disposer = host.on(eventHub, eventName, functionValue);
        if (typeof disposer === 'function') disposers.push(disposer);
    };

    add(HEADER_ACTION_EVENTS.define, (event: Event) => {
        const detail = getDetail(event);
        const id = getActionId(detail);
        if (!id) return;
        const definition = readDefinitionInput(detail?.definition);
        getHeaderActions().defineAction(id, definition);
    });

    add(HEADER_ACTION_EVENTS.update, (event: Event) => {
        const detail = getDetail(event);
        const id = getActionId(detail);
        if (!id) return;
        const context = getContextId(detail) || id;
        const state = readPayloadInput(detail?.state);
        if (!state) return;
        getHeaderActions().setActionState(id, context, state);
    });

    add(HEADER_ACTION_EVENTS.remove, (event: Event) => {
        const detail = getDetail(event);
        const id = getActionId(detail);
        if (!id) return;
        getHeaderActions().removeActionContext(id, getContextId(detail) || id);
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
