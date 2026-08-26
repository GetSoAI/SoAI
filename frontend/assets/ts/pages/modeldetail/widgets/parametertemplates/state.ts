/* SoAI - Model detail page widgets parameter templates state [frontend/assets/ts/pages/modeldetail/widgets/parametertemplates/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NamedParameter, ParameterDefinition, ParameterTemplateContext, ParameterTemplateOptions, ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';

type SupportedParameterType = 'boolean' | 'integer' | 'float' | 'array' | 'object' | 'string';

const resolveParameterDefinition = (definition?: ParameterDefinition | null): ParameterDefinition => definition ?? {};

const resolveParameterValue = (parameter: NamedParameter, definition: ParameterDefinition): ParameterValue | null => {
    const value = parameter.currentValue === null || parameter.currentValue === undefined ? definition.default : parameter.currentValue;
    if (value === undefined) {
        return null;
    }
    return value;
};

const normalizeParameterType = (value: JsonValue | undefined): SupportedParameterType => {
    switch (value) {
        case 'boolean':
        case 'integer':
        case 'float':
        case 'array':
        case 'object':
        case 'string':
            return value;
        default:
            return 'string';
    }
};

const resolveDescribeArray = (describeArray: ParameterTemplateOptions['describeArray']): ParameterTemplateContext['describeArray'] => {
    if (isFunction(describeArray)) {
        return describeArray;
    }
    return (itemType?: string): string => i18n.t('modelDetail.parameters.arrayOfType', { itemType: itemType ?? '' });
};

const resolveFormatGroupLabel = (formatGroupLabel: ParameterTemplateOptions['formatGroupLabel']): ParameterTemplateContext['formatGroupLabel'] => {
    if (formatGroupLabel) {
        return formatGroupLabel;
    }
    return (group?: string): string => {
        if (typeof group === 'string') {
            return group.toUpperCase();
        }
        return '';
    };
};

const createRenderContext = (options: ParameterTemplateOptions): ParameterTemplateContext => {
    const { categories, icons, isCustomized, describeArray, formatGroupLabel } = options;
    if (!isFunction(isCustomized)) {
        throw new TypeError('isCustomized must be a function');
    }
    if (!isObject(icons)) {
        throw new TypeError('Icons must be an object');
    }
    return {
        categories,
        icons,
        isCustomized,
        describeArray: resolveDescribeArray(describeArray),
        formatGroupLabel: resolveFormatGroupLabel(formatGroupLabel)
    };
};

export { createRenderContext, normalizeParameterType, resolveParameterDefinition, resolveParameterValue };
