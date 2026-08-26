/* SoAI - Shared UI external link trigger attributes [frontend/assets/ts/core/ui/externallinks/externalLinkTriggerAttributes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi } from '@core/security/public.ts';
import { isFunction, isNullOrUndefined, isString } from '@core/typeGuards.ts';

const CAMEL_CASE_PATTERN = /([A-Z])/g;

type ExternalLinkAttributeValue = string | number | boolean | null | undefined;

interface SecurityApi {
    escapeAttribute(value: string): string;
}

const getSecurity = (): SecurityApi => {
    if (!securityApi || typeof securityApi !== 'object') {
        throw new Error('Security API is unavailable');
    }
    const escapeAttribute = securityApi.escapeAttribute;
    if (!isFunction(escapeAttribute)) {
        throw new Error('Security API must expose escapeAttribute(value)');
    }
    return { escapeAttribute };
};

const mapDatasetToAttributes = (dataset: Record<string, ExternalLinkAttributeValue> = {}): Record<string, ExternalLinkAttributeValue> => {
    const attributes: Record<string, ExternalLinkAttributeValue> = {};
    for (const [rawKey, value] of Object.entries(dataset)) {
        if (isNullOrUndefined(value)) {
            continue;
        }
        const normalizedKey = `data-${String(rawKey).replace(CAMEL_CASE_PATTERN, '-$1').toLowerCase()}`;
        attributes[normalizedKey] = value;
    }
    return attributes;
};

const stringifyAttributes = (attributes: Record<string, ExternalLinkAttributeValue> = {}): string => {
    const security = getSecurity();
    return Object.entries(attributes)
        .filter(([, value]) => !isNullOrUndefined(value) && value !== false)
        .map(([name, value]) => {
            const renderedName = name.trim();
            if (!renderedName) {
                throw new Error('Attribute name must be non-empty');
            }
            const renderedValue = security.escapeAttribute(String(value));
            if (!isString(renderedValue)) {
                throw new Error('Security escapeAttribute must return a string');
            }
            return `${renderedName}="${renderedValue}"`;
        })
        .join(' ');
};

export interface ExternalLinkTriggerOptions {
    className?: string | undefined;
    dataset?: Record<string, ExternalLinkAttributeValue> | undefined;
    attributes?: Record<string, ExternalLinkAttributeValue> | undefined;
}

export const buildExternalLinkTriggerAttributes = ({ className = '', dataset = {}, attributes = {} }: ExternalLinkTriggerOptions = {}): string => {
    const mergedAttributes: Record<string, ExternalLinkAttributeValue> = {
        ...(className ? { class: className } : {}),
        ...attributes,
        ...mapDatasetToAttributes(dataset)
    };
    return stringifyAttributes(mergedAttributes);
};
