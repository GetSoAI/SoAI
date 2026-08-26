/* SoAI - Shared frontend layout header action zone manager mapping [frontend/assets/ts/core/layout/header/actionzonemanager/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isBoolean, isFiniteNumber, isFunction, isString } from '@core/typeGuards.ts';
import type { Renderable } from '@core/headeractions/public.ts';
import type { Action, HeaderActionInputValue } from '@core/layout/header/actionzonemanager/types.ts';

const resolveString = (value: HeaderActionInputValue): string => (isString(value) ? value : '');

const normalizeOptionalString = (value: HeaderActionInputValue): string | undefined => {
    if (!isString(value)) {
        return undefined;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
};

const normalizeOptionalBoolean = (value: HeaderActionInputValue): boolean | undefined => (isBoolean(value) ? value : undefined);

const normalizeOptionalNumber = (value: HeaderActionInputValue): number | undefined => (isFiniteNumber(value) ? value : undefined);

const normalizeAction = (value: Renderable | null | undefined): Action | null => {
    if (value === null || value === undefined) {
        return null;
    }

    const idValue = value['id'];
    if (!isString(idValue) || !idValue.trim()) {
        return null;
    }

    const onClickValue = value['onClick'];
    const onClick = isFunction(onClickValue)
        ? (event: Event): void => {
              onClickValue(event);
          }
        : undefined;

    return {
        id: idValue.trim(),
        visible: normalizeOptionalBoolean(value['visible']),
        disabled: normalizeOptionalBoolean(value['disabled']),
        label: normalizeOptionalString(value['label']),
        tooltip: normalizeOptionalString(value['tooltip']),
        ariaLabel: normalizeOptionalString(value['ariaLabel']),
        className: normalizeOptionalString(value['className']),
        badge: normalizeOptionalString(value['badge']),
        icon: normalizeOptionalString(value['icon']),
        pressed: normalizeOptionalBoolean(value['pressed']),
        order: normalizeOptionalNumber(value['order']),
        priority: normalizeOptionalNumber(value['priority']),
        onClick
    };
};

const normalizeActionArray = (value: readonly Renderable[] | null | undefined): Action[] => {
    if (!isArray(value)) {
        return [];
    }

    const actions: Action[] = [];
    for (const entry of value) {
        const normalized = normalizeAction(entry);
        if (normalized) {
            actions.push(normalized);
        }
    }
    return actions;
};

export { normalizeActionArray, resolveString };
