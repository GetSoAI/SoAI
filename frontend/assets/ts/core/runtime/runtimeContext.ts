/* SoAI - Shared runtime context [frontend/assets/ts/core/runtime/runtimeContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { constants, TIMEOUTS } from '@core/constants.ts';
import { domCache } from '@core/dom/dom.ts';
import { createDiagnostics, createModuleLogger, type DiagnosticsResult, type LogLevel, type ModuleLogger } from '@core/moduleContext.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';

interface DiagnosticsOptions {
    timeoutMs?: number | undefined;
    defaultLevel?: LogLevel | undefined;
}

interface ModuleLoggerOptions {
    defaultLevel?: LogLevel;
}

const getConstants = (): typeof constants => {
    return constants;
};

type TimeoutKey = keyof typeof TIMEOUTS;
type KernelServiceId = SoAIServiceId;
type KernelServiceValue = SoAIRegisteredService;

const getCoreTimeout = (key: TimeoutKey): number => {
    const value = TIMEOUTS[key];
    if (isFiniteNumber(value) && value > 0) return value;
    throw new Error(`Timeout configuration missing for ${String(key)}`);
};

const getDomCache = (): typeof domCache => domCache;

const isCanonicalServiceId = (value: string): boolean => value.startsWith('core.') || value.startsWith('features.') || value.startsWith('pages.');

const assertKernelServiceId = (identifier: string): string => {
    const token = assertNonEmptyString(identifier, 'Service identifier');
    if (!isCanonicalServiceId(token)) {
        throw new Error(`Kernel service id must be canonical (core.*, features.*, pages.*). Got '${token}'`);
    }
    return token;
};

function resolveKernelService<TServiceName extends KernelServiceId>(identifier: TServiceName): SoAIServiceRegistry[TServiceName];
function resolveKernelService(identifier: string): KernelServiceValue;
function resolveKernelService(identifier: string): KernelServiceValue {
    const token = assertKernelServiceId(identifier);
    const serviceContainer = getServiceContainer();
    if (serviceContainer.has(token)) {
        return serviceContainer.get(token);
    }
    throw new Error(`Unable to resolve kernel service: ${token}`);
}

const hasKernelService = (identifier: string): boolean => {
    const token = assertKernelServiceId(identifier);
    return getServiceContainer().has(token);
};

function resolveOptionalKernelService<TServiceName extends KernelServiceId>(identifier: TServiceName): SoAIServiceRegistry[TServiceName] | null;
function resolveOptionalKernelService(identifier: string): KernelServiceValue | null;
function resolveOptionalKernelService(identifier: string): KernelServiceValue | null {
    const token = assertKernelServiceId(identifier);
    const serviceContainer = getServiceContainer();
    if (!serviceContainer.has(token)) {
        return null;
    }
    return serviceContainer.get(token);
}

const createKernelResolver = (): ((identifier: string) => KernelServiceValue) => (identifier) => resolveKernelService(identifier);

const ensureDiagnostics = (name: string, options: DiagnosticsOptions = {}): DiagnosticsResult => {
    const merged = { ...options };
    if (!isFiniteNumber(merged.timeoutMs) || merged.timeoutMs <= 0) {
        merged.timeoutMs = getCoreTimeout('CORE_MODULES');
    }
    if (!isString(merged.defaultLevel) || !merged.defaultLevel) {
        merged.defaultLevel = 'warn';
    }
    return createDiagnostics(name, merged);
};

function waitForKernelService<TServiceName extends KernelServiceId>(identifier: TServiceName, options?: { timeoutMs?: number | undefined }): Promise<SoAIServiceRegistry[TServiceName]>;
function waitForKernelService(identifier: string, options?: { timeoutMs?: number | undefined }): Promise<KernelServiceValue>;
function waitForKernelService(identifier: string, options: { timeoutMs?: number | undefined } = {}): Promise<KernelServiceValue> {
    const token = assertKernelServiceId(identifier);
    const serviceContainer = getServiceContainer();
    const rawTimeoutMs = options.timeoutMs;
    const timeoutMs = typeof rawTimeoutMs === 'number' && Number.isFinite(rawTimeoutMs) && rawTimeoutMs > 0 ? rawTimeoutMs : getCoreTimeout('CORE_MODULES');
    return serviceContainer.waitFor(token, { timeoutMs });
}

const waitForKernelServices = (identifiers: string[], options: { timeoutMs?: number | undefined } = {}): Promise<KernelServiceValue[]> => {
    const serviceContainer = getServiceContainer();
    const rawTimeoutMs = options.timeoutMs;
    const timeoutMs = typeof rawTimeoutMs === 'number' && Number.isFinite(rawTimeoutMs) && rawTimeoutMs > 0 ? rawTimeoutMs : getCoreTimeout('CORE_MODULES');
    return Promise.all(identifiers.map((identifier) => serviceContainer.waitFor(assertKernelServiceId(identifier), { timeoutMs })));
};

export { createKernelResolver, createModuleLogger, ensureDiagnostics, getConstants, getCoreTimeout, getDomCache, hasKernelService, resolveOptionalKernelService, resolveKernelService, waitForKernelService, waitForKernelServices };

export type { LogLevel, DiagnosticsOptions, ModuleLoggerOptions, ModuleLogger, TimeoutKey };
