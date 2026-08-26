/* SoAI - Shared header actions state [frontend/assets/ts/core/headeractions/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLanguageService } from '@core/languageservice/service.ts';
import { DEFAULT_ORDER, DEFAULT_PRIORITY } from '@core/headeractions/constants.ts';
import { isFiniteNumber, isFunction, isString } from '@core/typeGuards.ts';

import type { ActionDefinition, ActionSnapshot, ContextPayload, DefinitionInput, PayloadInput, RegistryEntry, Renderable } from '@core/headeractions/types.ts';

const now = (): number => Date.now();

const normalizeActionId = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error('Header action id must be a non-empty string');
    }
    return trimmed;
};

const normalizeNullableString = (value: string | undefined): string | null => {
    if (!isString(value)) {
        return null;
    }
    return value;
};

const createBaseDefinition = (definition: DefinitionInput = {}): ActionDefinition => {
    const order = isFiniteNumber(definition.order) ? definition.order : DEFAULT_ORDER;
    const priority = isFiniteNumber(definition.priority) ? definition.priority : DEFAULT_PRIORITY;
    return {
        id: definition.id ?? '',
        order,
        priority,
        icon: normalizeNullableString(definition.icon),
        label: normalizeNullableString(definition.label),
        tooltip: normalizeNullableString(definition.tooltip),
        ariaLabel: normalizeNullableString(definition.ariaLabel),
        className: isString(definition.className) ? definition.className : '',
        persistent: definition.persistent === true,
        disabled: definition.disabled === true,
        badge: normalizeNullableString(definition.badge),
        analyticsId: normalizeNullableString(definition.analyticsId),
        pressed: definition.pressed === undefined ? null : definition.pressed === true
    };
};

const selectActiveContext = (entry: RegistryEntry): ContextPayload | null => {
    const candidates: ContextPayload[] = [];
    entry.contexts.forEach((context) => {
        if (context.visible) {
            candidates.push(context);
        }
    });
    if (!candidates.length) {
        return null;
    }
    candidates.sort((left, right) => {
        if (left.priority !== right.priority) {
            return left.priority - right.priority;
        }
        return right.updatedAt - left.updatedAt;
    });
    return candidates[0] ?? null;
};

const deriveRenderable = (entry: RegistryEntry): Renderable => {
    const base = entry.definition;
    const active = selectActiveContext(entry);
    const onClick = active?.onClick ?? base.onClick ?? null;
    return {
        id: entry.id,
        visible: Boolean((active?.visible ?? false) || base.persistent),
        icon: active?.icon ?? base.icon,
        label: active?.label ?? base.label ?? null,
        tooltip: active?.tooltip ?? base.tooltip ?? null,
        ariaLabel: active?.ariaLabel ?? base.ariaLabel ?? null,
        className: active?.className ?? base.className,
        disabled: active?.disabled ?? base.disabled,
        badge: active?.badge ?? base.badge,
        analyticsId: active?.analyticsId ?? base.analyticsId,
        pressed: active?.pressed ?? base.pressed,
        order: isFiniteNumber(active?.order) ? active.order : base.order,
        priority: isFiniteNumber(active?.priority) ? active.priority : base.priority,
        onClick
    };
};

const renderableChanged = (previous: Renderable | null, next: Renderable): boolean => {
    if (!previous) {
        return true;
    }
    return previous.visible !== next.visible || previous.icon !== next.icon || previous.label !== next.label || previous.tooltip !== next.tooltip || previous.ariaLabel !== next.ariaLabel || previous.className !== next.className || previous.disabled !== next.disabled || previous.badge !== next.badge || previous.analyticsId !== next.analyticsId || previous.pressed !== next.pressed || previous.order !== next.order || previous.priority !== next.priority || previous.onClick !== next.onClick;
};

const cloneRenderable = (renderable: Renderable | null): Renderable | null => {
    if (!renderable) {
        return null;
    }
    return { ...renderable };
};

const normalizeContextPayload = (payload: PayloadInput = {}): ContextPayload => ({
    visible: payload.visible === true,
    priority: isFiniteNumber(payload.priority) ? payload.priority : DEFAULT_PRIORITY,
    order: isFiniteNumber(payload.order) ? payload.order : null,
    icon: normalizeNullableString(payload.icon),
    label: normalizeNullableString(payload.label),
    tooltip: normalizeNullableString(payload.tooltip),
    ariaLabel: normalizeNullableString(payload.ariaLabel),
    className: normalizeNullableString(payload.className),
    disabled: payload.disabled === true,
    badge: normalizeNullableString(payload.badge),
    analyticsId: normalizeNullableString(payload.analyticsId),
    pressed: payload.pressed === undefined ? null : payload.pressed === true,
    onClick: isFunction(payload.onClick) ? payload.onClick : null,
    updatedAt: now()
});

const sortRenderables = (actions: Renderable[]): Renderable[] =>
    actions.sort((left, right) => {
        if (left.order !== right.order) {
            return left.order - right.order;
        }
        if (left.priority !== right.priority) {
            return left.priority - right.priority;
        }
        return left.id.localeCompare(right.id, getLanguageService().getLocale());
    });

const createActionSnapshot = (registry: Map<string, RegistryEntry>): ActionSnapshot => {
    const actions: Renderable[] = [];
    registry.forEach((entry) => {
        const renderable = cloneRenderable(entry.renderable);
        if (renderable) {
            actions.push(renderable);
        }
    });
    return {
        actions: sortRenderables(actions)
    };
};

export { normalizeActionId, createBaseDefinition, deriveRenderable, renderableChanged, normalizeContextPayload, createActionSnapshot, cloneRenderable };
