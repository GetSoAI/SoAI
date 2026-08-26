/* SoAI - Shared frontend routing pages collections resource mapping [frontend/assets/ts/core/routing/pages/collections/resource/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { isFunction, isPlainObject, isString } from '@core/typeGuards.ts';
import type { ActionHandlerConfig, DelegatedHandlerConfig } from '@core/routing/pages/collections/types.ts';

const parseNonEmptyString = <T>(value: T | null | undefined, context: string): string => {
    if (!isString(value)) {
        throw new TypeError(`${context} must be a string`);
    }
    const trimmed = value.trim();
    if (!trimmed) {
        throw new TypeError(`${context} must be a non-empty string`);
    }
    return trimmed;
};

const parseActionHandlerConfigList = (values: readonly ActionHandlerConfig[], context: string): ActionHandlerConfig[] => {
    const configs: ActionHandlerConfig[] = [];
    values.forEach((value, index) => {
        if (!isPlainObject(value)) {
            throw new TypeError(`${context}[${index}] must be an object`);
        }
        const selector = parseNonEmptyString(value['selector'], `${context}[${index}].selector`);
        const handlerValue = value['handler'];
        if (!isFunction(handlerValue)) {
            throw new TypeError(`${context}[${index}].handler must be a function`);
        }
        const eventValue = value['event'];
        const event = eventValue === undefined ? undefined : parseNonEmptyString(eventValue, `${context}[${index}].event`);

        const preventDefaultValue = value['preventDefault'];
        let preventDefault: boolean | undefined;
        if (preventDefaultValue !== undefined && typeof preventDefaultValue !== 'boolean') {
            throw new TypeError(`${context}[${index}].preventDefault must be a boolean`);
        }
        if (typeof preventDefaultValue === 'boolean') {
            preventDefault = preventDefaultValue;
        }
        const stopPropagationValue = value['stopPropagation'];
        let stopPropagation: boolean | undefined;
        if (stopPropagationValue !== undefined && typeof stopPropagationValue !== 'boolean') {
            throw new TypeError(`${context}[${index}].stopPropagation must be a boolean`);
        }
        if (typeof stopPropagationValue === 'boolean') {
            stopPropagation = stopPropagationValue;
        }
        const optionalValue = value['optional'];
        let optional: boolean | undefined;
        if (optionalValue !== undefined && typeof optionalValue !== 'boolean') {
            throw new TypeError(`${context}[${index}].optional must be a boolean`);
        }
        if (typeof optionalValue === 'boolean') {
            optional = optionalValue;
        }

        configs.push({
            selector,
            handler: handlerValue,
            event,
            preventDefault,
            stopPropagation,
            optional
        });
    });
    return configs;
};

const parseDelegatedHandlerConfigList = (values: readonly DelegatedHandlerConfig[], context: string): DelegatedHandlerConfig[] => {
    const configs: DelegatedHandlerConfig[] = [];
    values.forEach((value, index) => {
        if (!isPlainObject(value)) {
            throw new TypeError(`${context}[${index}] must be an object`);
        }
        const container = parseNonEmptyString(value['container'], `${context}[${index}].container`);
        const selector = parseNonEmptyString(value['selector'], `${context}[${index}].selector`);
        const handlerValue = value['handler'];
        if (!isFunction(handlerValue)) {
            throw new TypeError(`${context}[${index}].handler must be a function`);
        }
        const eventValue = value['event'];
        const event = eventValue === undefined ? undefined : parseNonEmptyString(eventValue, `${context}[${index}].event`);

        configs.push({ container, selector, handler: handlerValue, event });
    });
    return configs;
};

const createLayoutAbortError = (pageId: string, identifier: string | null, reason: string): Error => {
    const scope = identifier ? `${pageId} ${identifier}` : pageId;
    const suffix = reason ? `: ${reason}` : '';
    return createAbortError(`${scope} layout wait aborted${suffix}`);
};

export { createLayoutAbortError, parseActionHandlerConfigList, parseDelegatedHandlerConfigList, parseNonEmptyString };
