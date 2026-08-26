/* SoAI - Model detail page contract boundary parameter types [frontend/assets/ts/pages/modeldetail/contracts/parameterTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ParameterValue = JsonValue;

type ParameterType = 'string' | 'integer' | 'float' | 'boolean' | 'array' | 'object' | (string & {});

type ParameterDefinition = {
    displayName?: string | undefined;
    category?: string | undefined;
    group?: string | undefined;
    description?: string | undefined;
    aliases?: string[] | undefined;
    linkedParameterName?: string | undefined;
    isStandardizedAlias?: boolean | undefined;
    requiresReload?: boolean | undefined;
    default?: ParameterValue;
    hasDefault?: boolean | undefined;
    type?: ParameterType | undefined;
    itemType?: string | undefined;
    minimum?: number | undefined;
    maximum?: number | undefined;
    numericStringMinimum?: number | undefined;
    numericStringMaximum?: number | undefined;
    valueCount?: number | undefined;
    choices?: ParameterValue[] | undefined;
};

type Parameter = {
    definition?: ParameterDefinition | undefined;
    currentValue?: ParameterValue | undefined;
    isCustom?: boolean | undefined;
    hasDefault?: boolean | undefined;
};

type ParameterCategoryDefinition = {
    title?: string | undefined;
    description?: string | undefined;
};

type ParameterCategory = string | ParameterCategoryDefinition;

type NamedParameter = Parameter & { key: string };

type ParameterCollection = Record<string, Parameter>;

type ParametersPayload = {
    universalId?: string | undefined;
    plugin?: string | undefined;
    sourceModelId?: string | undefined;
    parameterVersion?: number | undefined;
    parameters?: ParameterCollection | undefined;
    categories?: Record<string, ParameterCategory> | undefined;
};

interface ParameterTemplateOptions {
    categories?: Record<string, ParameterCategory> | undefined;
    icons: Record<string, TrustedHtml>;
    isCustomized: (parameter: string | NamedParameter) => boolean;
    describeArray?: (itemType?: string) => string;
    formatGroupLabel?: (group?: string) => string;
}

interface ParameterTemplateContext {
    categories?: Record<string, ParameterCategory> | undefined;
    icons: Record<string, TrustedHtml>;
    isCustomized: (parameter: string | NamedParameter) => boolean;
    describeArray: (itemType?: string) => string;
    formatGroupLabel: (group?: string) => string;
}

export type { Parameter, ParameterCategory, ParameterCategoryDefinition, ParameterCollection, ParameterDefinition, ParameterTemplateContext, ParameterTemplateOptions, ParameterType, ParameterValue, ParametersPayload, NamedParameter };
