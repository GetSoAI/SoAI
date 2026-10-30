/* SoAI - Shared frontend layout header action zone manager effects [frontend/assets/ts/core/layout/header/actionzonemanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { Action, ActionEntry, ActionZoneManagerHost, ActionZoneManagerState } from '@core/layout/header/actionzonemanager/types.ts';
import { resolveString } from '@core/layout/header/actionzonemanager/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { syncAttributeValue } from '@core/dom/patching.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const BUTTON_BASE_CLASS = 'header-action-button';
const ICON_SELECTOR = '.header-action-icon';
const BADGE_SELECTOR = '.header-action-badge';

const createActionEntry = (id: string): ActionEntry => {
    const icon = dom.create('span', {
        className: `ui-icon ${ICON_SELECTOR.slice(1)}`
    });

    const badge = dom.create('span', {
        className: BADGE_SELECTOR.slice(1),
        hidden: true,
        dataset: { presence: '' }
    });

    const element = dom.create('button', {
        type: 'button',
        className: `ui-icon-button ${BUTTON_BASE_CLASS}`,
        dataset: { actionId: id }
    });
    if (!(element instanceof HTMLButtonElement)) {
        throw new Error('Header action entry requires a button element');
    }

    dom.appendChild(element, [icon, badge]);

    return {
        id,
        element,
        icon,
        badge,
        requestedIcon: null,
        renderedIcon: null,
        declarativeClassNames: new Set(['ui-icon-button', BUTTON_BASE_CLASS]),
        iconApplyInFlight: false,
        cleanup: null,
        handler: null
    };
};

const removeActionEntry = (state: ActionZoneManagerState, id: string): void => {
    const entry = state.actions.get(id);
    if (!entry) {
        return;
    }
    if (isFunction(entry.cleanup)) {
        entry.cleanup();
        entry.cleanup = null;
        entry.handler = null;
    }
    if (state.container && entry.element.parentElement === state.container) {
        removeWithPresence(entry.element);
    } else {
        state.actions.delete(id);
    }
};

const applyRequestedIcon = (header: ActionZoneManagerHost, entry: ActionEntry, actionId: string): void => {
    if (entry.iconApplyInFlight) {
        return;
    }
    const icon = entry.requestedIcon;
    if (!icon || entry.renderedIcon === icon) {
        return;
    }
    entry.iconApplyInFlight = true;
    const applyIcon = async (): Promise<void> => {
        let applied = false;
        try {
            await header.icons.apply([
                {
                    element: entry.element,
                    selector: ICON_SELECTOR,
                    icon,
                    replace: true
                }
            ]);
            entry.renderedIcon = icon;
            applied = true;
        } catch (error) {
            ensureError(error);
            header.logger('warn', 'Failed to render header action icon', { id: actionId, error });
        } finally {
            entry.iconApplyInFlight = false;
            if (applied && !entry.requestedIcon) {
                entry.renderedIcon = null;
                entry.icon.textContent = '';
                return;
            }
            if (applied && entry.requestedIcon && entry.renderedIcon !== entry.requestedIcon) {
                applyRequestedIcon(header, entry, actionId);
            }
        }
    };
    terminateHandledPromise(applyIcon());
};

const updateActionEntry = (state: ActionZoneManagerState, header: ActionZoneManagerHost, entry: ActionEntry, action: Action): void => {
    const label = resolveString(action.label);
    const tooltipText = resolveString(action.tooltip);
    const ariaLabel = resolveString(action.ariaLabel);
    const className = resolveString(action.className);

    syncAttributeValue(entry.element, 'data-action-id', action.id);
    const disabled = Boolean(action.disabled);
    if (entry.element.disabled !== disabled) entry.element.disabled = disabled;
    syncAttributeValue(entry.element, 'type', 'button');
    syncAttributeValue(entry.element, 'aria-label', ariaLabel || label || tooltipText);
    syncAttributeValue(entry.element, 'aria-pressed', action.pressed === null || action.pressed === undefined ? null : action.pressed ? 'true' : 'false');

    setTooltipText(entry.element, tooltipText);

    const declarativeClassNames = new Set(['ui-icon-button', BUTTON_BASE_CLASS, ...className.split(/[\t\n\f\r ]+/u).filter(Boolean)]);
    const retainedClassNames = Array.from(entry.element.classList).filter((name) => !entry.declarativeClassNames.has(name) && !declarativeClassNames.has(name));
    syncAttributeValue(entry.element, 'class', [...declarativeClassNames, ...retainedClassNames].join(' '));
    entry.declarativeClassNames = declarativeClassNames;

    const badgeValue = resolveString(action.badge);
    if (badgeValue) {
        header.updateText(entry.badge, badgeValue);
        entry.badge.hidden = false;
    } else {
        entry.badge.hidden = true;
        entry.badge.textContent = '';
    }

    if (action.visible) {
        const container = state.container;
        if (!container) {
            throw new Error('ActionZoneManager container is required to render visible actions');
        }
        insertWithPresence(container, entry.element);
        const icon = action.icon;
        if (icon) {
            entry.requestedIcon = icon;
            applyRequestedIcon(header, entry, action.id);
        } else {
            entry.requestedIcon = null;
            entry.renderedIcon = null;
            entry.icon.textContent = '';
        }
    } else {
        if (state.container && entry.element.parentElement === state.container) {
            removeWithPresence(entry.element);
        }
    }

    if (isFunction(entry.cleanup)) {
        entry.cleanup();
        entry.cleanup = null;
        entry.handler = null;
    }

    const onClick = action.onClick;
    if (action.visible && !entry.element.disabled && typeof onClick === 'function') {
        const handler = (event: Event): void => {
            event.preventDefault();
            if (entry.element.disabled) {
                return;
            }
            onClick(event);
        };
        entry.handler = onClick;
        const cleanup = header.on(entry.element, 'click', handler);
        entry.cleanup = isFunction(cleanup) ? cleanup : null;
    }
};

const reorderVisibleActions = (state: ActionZoneManagerState, actions: Action[]): void => {
    if (!actions.length || !state.container) {
        return;
    }
    const container = state.container;

    const ordered = [...actions].sort((firstValue, secondValue) => {
        if (firstValue.order !== secondValue.order) {
            return (firstValue.order ?? 0) - (secondValue.order ?? 0);
        }
        if (firstValue.priority !== secondValue.priority) {
            return (firstValue.priority ?? 0) - (secondValue.priority ?? 0);
        }
        return firstValue.id.localeCompare(secondValue.id, getLanguageService().getLocale());
    });

    const orderedElements = ordered.map((action) => state.actions.get(action.id)?.element).filter((element): element is HTMLButtonElement => element?.parentElement === container);
    const currentElements = Array.from(container.children).filter((child) => orderedElements.some((element) => element === child));
    if (currentElements.every((element, index) => element === orderedElements[index])) {
        return;
    }
    orderedElements.forEach((element) => container.appendChild(element));
};

const updateActionZoneEmptyState = (state: ActionZoneManagerState, header: ActionZoneManagerHost, hiddenClass: string, visibleActions: Action[]): void => {
    if (!state.container) {
        return;
    }

    const hasVisible = visibleActions.some((action) => action.visible);
    if (hasVisible) {
        header.removeClassName(state.container, hiddenClass);
        state.container.removeAttribute('aria-hidden');
    } else {
        header.addClassName(state.container, hiddenClass);
        header.updateAttribute(state.container, 'aria-hidden', 'true');
    }
};

const validateActionZoneManagerDependencies = (header: ActionZoneManagerHost, hiddenClass: string): void => {
    if (!header || !isFunction(header.on) || !header.icons) {
        throw new Error('ActionZoneManager requires a header with event binding and icon support');
    }
    if (!isString(hiddenClass) || !hiddenClass.trim()) {
        throw new Error('ActionZoneManager requires a hidden class name');
    }
};

const syncActionEntries = (state: ActionZoneManagerState, header: ActionZoneManagerHost, actions: Action[]): Action[] => {
    const visibleActions: Action[] = [];
    const seen = new Set<string>();

    actions.forEach((action) => {
        if (!isObject(action) || !isString(action.id)) {
            return;
        }

        seen.add(action.id);
        const entry = state.actions.get(action.id) || createActionEntry(action.id);
        state.actions.set(action.id, entry);
        updateActionEntry(state, header, entry, action);
        if (action.visible) {
            visibleActions.push(action);
        }
    });

    state.actions.forEach((_unusedValue, id) => {
        if (!seen.has(id)) {
            removeActionEntry(state, id);
        }
    });

    return visibleActions;
};

const destroyActionEntries = (state: ActionZoneManagerState): void => {
    if (isFunction(state.layoutCleanup)) {
        state.layoutCleanup();
        state.layoutCleanup = null;
    }
    const container = state.container;
    state.actions.forEach((entry) => {
        if (isFunction(entry.cleanup)) {
            entry.cleanup();
        }
        if (container && entry.element.parentElement === container) {
            container.removeChild(entry.element);
        }
    });
    state.actions.clear();
};

export { destroyActionEntries, reorderVisibleActions, syncActionEntries, updateActionZoneEmptyState, validateActionZoneManagerDependencies };
