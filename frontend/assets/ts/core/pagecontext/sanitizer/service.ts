/* SoAI - Shared page context sanitizer service [frontend/assets/ts/core/pagecontext/sanitizer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizeUrlOptions } from '@core/security/urlSanitizer.ts';
import type { SanitizerApi, SanitizerInput, SecurityService } from '@core/pagecontext/contracts.ts';
import { isObject } from '@core/typeGuards.ts';

type SecurityServiceCandidate = Partial<SecurityService>;

const sanitizeClassName = (value: SanitizerInput, fallback: string = '', { allowEmpty = false }: { allowEmpty?: boolean } = {}): string => {
    if (value == null) {
        if (allowEmpty) {
            return '';
        }
        throw new Error('PageContext sanitizer.className requires a value');
    }
    const sanitized = String(value)
        .trim()
        .replace(/[^A-Za-z0-9_-]/g, '-');
    if (!sanitized && !allowEmpty && !fallback) {
        throw new Error('PageContext sanitizer.className produced an empty value');
    }
    return (sanitized || fallback) ?? '';
};

const isSecurityServiceCandidate = <T>(value: T): value is T & SecurityServiceCandidate => isObject(value);
const isSanitizeTextFunction = <T>(value: T): value is T & SecurityService['sanitizeText'] => typeof value === 'function';
const isEscapeHtmlFunction = <T>(value: T): value is T & SecurityService['escapeHtml'] => typeof value === 'function';
const isEscapeAttributeFunction = <T>(value: T): value is T & SecurityService['escapeAttribute'] => typeof value === 'function';
const isSanitizeUrlFunction = <T>(value: T): value is T & SecurityService['sanitizeUrl'] => typeof value === 'function';
const isSanitizeAbsoluteHttpUrlFunction = <T>(value: T): value is T & SecurityService['sanitizeAbsoluteHttpUrl'] => typeof value === 'function';
const isSanitizeImageSourceFunction = <T>(value: T): value is T & SecurityService['sanitizeImageSource'] => typeof value === 'function';

const createSanitizerApi = <T>(security: T): SanitizerApi => {
    if (!security) {
        throw new Error('PageContext requires a security service');
    }
    if (!isSecurityServiceCandidate(security)) throw new Error('Security service must expose sanitizeText');
    const sanitizeTextValue = security.sanitizeText;
    const escapeHtmlValue = security.escapeHtml;
    const escapeAttributeValue = security.escapeAttribute;
    const sanitizeUrlValue = security.sanitizeUrl;
    const sanitizeAbsoluteHttpUrlValue = security.sanitizeAbsoluteHttpUrl;
    const sanitizeImageSourceValue = security.sanitizeImageSource;
    if (!isSanitizeTextFunction(sanitizeTextValue)) throw new Error('Security service must expose sanitizeText');
    if (!isEscapeHtmlFunction(escapeHtmlValue)) throw new Error('Security service must expose escapeHtml');
    if (!isEscapeAttributeFunction(escapeAttributeValue)) throw new Error('Security service must expose escapeAttribute');
    if (!isSanitizeUrlFunction(sanitizeUrlValue)) throw new Error('Security service must expose sanitizeUrl');
    if (!isSanitizeAbsoluteHttpUrlFunction(sanitizeAbsoluteHttpUrlValue)) throw new Error('Security service must expose sanitizeAbsoluteHttpUrl');
    if (!isSanitizeImageSourceFunction(sanitizeImageSourceValue)) throw new Error('Security service must expose sanitizeImageSource');

    const securityService: SecurityService = {
        sanitizeText: sanitizeTextValue,
        escapeHtml: escapeHtmlValue,
        escapeAttribute: escapeAttributeValue,
        sanitizeUrl: sanitizeUrlValue,
        sanitizeAbsoluteHttpUrl: sanitizeAbsoluteHttpUrlValue,
        sanitizeImageSource: sanitizeImageSourceValue
    };

    const requiredText = (value: SanitizerInput, options: { allowEmpty?: boolean } = {}): string => {
        if (value == null) {
            throw new Error('Sanitizer requires a value');
        }
        const result = securityService.sanitizeText(value, options);
        if (typeof result !== 'string') {
            throw new Error('Sanitizer must return a string');
        }
        if (!result && options.allowEmpty !== true) {
            throw new Error('Sanitizer requires a non-empty value');
        }
        return result;
    };

    const optionalText = (value: SanitizerInput, options: { allowEmpty?: boolean } = {}): string | null => {
        if (value == null) {
            return null;
        }
        const result = securityService.sanitizeText(value, { ...options, allowEmpty: true });
        if (typeof result !== 'string') {
            throw new Error('Sanitizer must return a string');
        }
        return result;
    };

    return Object.freeze({
        text: requiredText,
        optionalText,
        html: (value: SanitizerInput = ''): string => {
            const result = securityService.escapeHtml(value);
            if (typeof result !== 'string') throw new Error('Sanitizer html must return a string');
            return result;
        },
        attribute: (value: SanitizerInput = ''): string => {
            const result = securityService.escapeAttribute(value);
            if (typeof result !== 'string') throw new Error('Sanitizer attribute must return a string');
            return result;
        },
        url: (value: SanitizerInput, options: SanitizeUrlOptions = {}): string | null => {
            const result = securityService.sanitizeUrl(value, options);
            if (result === null) return null;
            if (typeof result !== 'string') throw new Error('Sanitizer url must return a string or null');
            return result;
        },
        absoluteHttpUrl: (value: SanitizerInput): string | null => {
            const result = securityService.sanitizeAbsoluteHttpUrl(value);
            if (result === null) return null;
            if (typeof result !== 'string') throw new Error('Sanitizer absoluteHttpUrl must return a string or null');
            return result;
        },
        image: (value: SanitizerInput): string | null => {
            const result = securityService.sanitizeImageSource(value);
            if (result === null) return null;
            if (typeof result !== 'string') throw new Error('Sanitizer image must return a string or null');
            return result;
        },
        className: sanitizeClassName
    });
};

export { createSanitizerApi };
