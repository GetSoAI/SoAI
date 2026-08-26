/* SoAI - Shared runtime environment mappers [frontend/assets/ts/core/runtimeenv/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseDetachedQuery } from '@core/runtime/detachedQuery.ts';
import { deepClone } from '@core/primitives/clone.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { hasOwn, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import type { DetachedContext, WindowMetadata } from '@core/runtimeenv/internalContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RuntimeEnvLogger {
    logDetachedWarning: (message: string, details?: TelemetryValue) => void;
}

const isValidRuntimeString = (value: JsonValue): value is string => {
    return isString(value) && Boolean(value.trim());
};

const trimRuntimeString = (value: string): string => {
    return value.trim();
};

const sanitizeDetachedParameters = (parameters: JsonValue, logger: RuntimeEnvLogger): JsonObject => {
    if (!isPlainObject(parameters)) {
        logger.logDetachedWarning('Detached window parameters must be an object', { parameters });
        throw new TypeError('Detached window parameters must be an object');
    }
    let cloned: JsonValue = null;
    try {
        cloned = deepClone(parameters);
    } catch (error) {
        const runtimeError = ensureError(error);
        logger.logDetachedWarning('Detached window parameters cloning failed', runtimeError);
        throw ensureError(error);
    }
    if (!isJsonObject(cloned)) {
        logger.logDetachedWarning('Detached window parameters cloning produced invalid data');
        throw new TypeError('Detached window parameters cloning produced invalid data');
    }
    return cloned;
};

const sanitizeDetachedWindowUrl = (value: JsonValue, logger: RuntimeEnvLogger): string => {
    if (!isString(value) || !value.trim()) {
        throw new Error('Detached window URL must be a non-empty string');
    }
    const url = value.trim();
    const lower = url.toLowerCase();
    const disallowedSchemes = ['javascript:', 'data:', 'vbscript:'];
    for (const scheme of disallowedSchemes) {
        if (lower.startsWith(scheme)) {
            logger.logDetachedWarning('Detached window URL uses a disallowed scheme', { url });
            throw new Error('Detached window URL is unsafe');
        }
    }
    if (lower.startsWith('http:') || lower.startsWith('https:') || url.startsWith('//')) {
        logger.logDetachedWarning('Detached window URL must be relative', { url });
        throw new Error('Detached window URL must be relative');
    }
    const allowedPrefixes = ['detached.html', './detached.html', '/detached.html'];
    const targetsDetachedPage = allowedPrefixes.some((prefix) => url === prefix || url.startsWith(`${prefix}?`));
    if (!targetsDetachedPage) {
        logger.logDetachedWarning('Detached window URL must target detached.html', { url });
        throw new Error('Detached window URL must target detached.html');
    }
    return url;
};

const normalizeWindowMetadata = (metadata: JsonValue, logger: RuntimeEnvLogger): WindowMetadata | null => {
    if (!isPlainObject(metadata)) {
        return null;
    }
    const rawPageId = metadata['pageId'];
    const pageId = isString(rawPageId) ? rawPageId.trim() || null : null;
    const rawParameters = hasOwn(metadata, 'parameters') ? metadata['parameters'] : {};
    return { pageId, parameters: sanitizeDetachedParameters(rawParameters ?? {}, logger) };
};

const serializeDetachedContext = (context: DetachedContext): JsonObject => {
    return {
        windowId: context.windowId,
        metadata: context.metadata,
        timestamp: context.timestamp,
        state: context.state
    };
};

const parseDetachedContextPayload = (payload: JsonValue, logger: RuntimeEnvLogger): DetachedContext | null => {
    if (!isPlainObject(payload)) {
        return null;
    }
    const rawWindowId = payload['windowId'] ?? null;
    if (!isValidRuntimeString(rawWindowId)) {
        return null;
    }
    const windowId = trimRuntimeString(rawWindowId);

    const timestampValue = payload['timestamp'];
    if (!isNumber(timestampValue) || !Number.isFinite(timestampValue) || timestampValue < 0) {
        return null;
    }

    const metadata = normalizeWindowMetadata(payload['metadata'] ?? null, logger);
    if (!metadata) {
        return null;
    }

    const stateValue = payload['state'] ?? null;
    if (!isJsonObject(stateValue)) {
        return null;
    }

    return { windowId, metadata, timestamp: timestampValue, state: stateValue };
};

const extractCurrentWindowMetadata = (search: string): WindowMetadata => {
    const { pageId } = parseDetachedQuery(search);
    return { pageId: pageId ?? null, parameters: {} };
};

const validateWindowIdentifier = (windowId: JsonValue, contextMessage: string, logger: RuntimeEnvLogger): string | null => {
    if (!isValidRuntimeString(windowId)) {
        logger.logDetachedWarning(`${contextMessage} requires a window identifier`, { windowId });
        return null;
    }
    return trimRuntimeString(windowId);
};

export { extractCurrentWindowMetadata, isValidRuntimeString, normalizeWindowMetadata, parseDetachedContextPayload, sanitizeDetachedParameters, sanitizeDetachedWindowUrl, serializeDetachedContext, trimRuntimeString, validateWindowIdentifier };
