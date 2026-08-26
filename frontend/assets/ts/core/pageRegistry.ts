/* SoAI - Shared frontend page registry [frontend/assets/ts/core/pageRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

type PageConstructor = { new (...inputArguments: never[]): PageInstance; prototype: PageInstance };

const isPageConstructor = (value: PageConstructor | JsonValue | null | undefined): value is PageConstructor => {
    if (typeof value !== 'function') {
        return false;
    }
    const protoCandidate = value['prototype'];
    return isObject(protoCandidate);
};

interface PageOptions {
    factory?: (() => PageInstance) | null;
}

interface PageMeta {
    name: string;
    PageClass: PageConstructor;
    options: PageOptions;
}

const defaultOptions: PageOptions = Object.freeze({
    factory: null
});

const normalizeName = (value: string): string => {
    return assertNonEmptyString(String(value), 'Page name', {
        ErrorType: TypeError
    });
};

const emitPageRegistryEvent = (stage: string, data: Record<string, string | number | boolean | null> = {}, severity: string = 'info'): void => {
    telemetry.emit({
        module: 'PageRegistry',
        stage,
        severity,
        message: stage,
        data
    });
};

const validatePageClass = (identifier: string, PageClass: PageConstructor): void => {
    const protoCandidate = PageClass.prototype;

    const isStatic = protoCandidate instanceof StaticBasePage;

    if (!isStatic) {
        throw new TypeError(`Page "${identifier}" must extend StaticBasePage. Current inheritance chain is invalid.`);
    }

    const renderMethod = protoCandidate.render;
    if (!isFunction(renderMethod)) {
        throw new TypeError(`Static page "${identifier}" must provide a render() method`);
    }

    const renderViewMethod = protoCandidate.renderView;
    if (!isFunction(renderViewMethod)) {
        throw new TypeError(`Static page "${identifier}" must implement renderView(context) - abstract method not overridden`);
    }

    const getRequiredResources = protoCandidate.getRequiredResources;
    if (!isFunction(getRequiredResources)) {
        throw new TypeError(`Static page "${identifier}" must implement getRequiredResources() - abstract method not overridden`);
    }
};

class PageRegistry {
    pages: Map<string, PageMeta>;

    constructor() {
        this.pages = new Map();
    }

    register(name: string, PageClass: PageConstructor | JsonValue | null | undefined, options: Partial<PageOptions> = {}): PageConstructor {
        const identifier = normalizeName(name);
        if (!isPageConstructor(PageClass)) {
            throw new TypeError(`register("${identifier}") expects a constructor function`);
        }
        const ctor = PageClass;
        if (this.pages.has(identifier)) {
            throw new Error(`Page "${identifier}" is already registered`);
        }
        validatePageClass(identifier, ctor);
        const mergedOptions: PageOptions = { ...defaultOptions, ...options };
        const meta: PageMeta = {
            name: identifier,
            PageClass: ctor,
            options: mergedOptions
        };
        this.pages.set(identifier, meta);
        return ctor;
    }

    has(name: string): boolean {
        const identifier = normalizeName(name);
        return this.pages.has(identifier);
    }

    get(name: string): PageConstructor | null {
        const identifier = normalizeName(name);
        const meta = this.pages.get(identifier);
        return meta ? meta.PageClass : null;
    }

    getMeta(name: string): PageMeta | null {
        const identifier = normalizeName(name);
        return this.pages.get(identifier) || null;
    }

    create(name: string): PageInstance | null {
        const identifier = normalizeName(name);
        const meta = this.pages.get(identifier);
        if (!meta) {
            return null;
        }
        return this.#instantiate(meta);
    }

    getAll(): Record<string, PageConstructor> {
        const result: Record<string, PageConstructor> = {};
        for (const [name, meta] of this.pages) {
            result[name] = meta.PageClass;
        }
        return result;
    }

    getAllNames(): string[] {
        return Array.from(this.pages.keys());
    }

    #instantiate = (meta: PageMeta): PageInstance => {
        const { PageClass, options } = meta;
        emitPageRegistryEvent('instantiate:start', { page: meta.name });
        let instance: PageInstance | null = null;
        const factory = options.factory;
        if (typeof factory === 'function') {
            instance = factory();
        } else {
            instance = new PageClass();
        }
        emitPageRegistryEvent('instantiate:created', { page: meta.name });
        emitPageRegistryEvent('instantiate:complete', { page: meta.name });
        if (!isObject(instance)) {
            throw new Error(`Page "${meta.name}" factory returned an invalid instance`);
        }
        return instance;
    };
}

const PAGE_REGISTRY_SERVICE_ID = 'core.pageRegistry';

const isPageRegistry = (value: PageRegistry | JsonValue | null | undefined): value is PageRegistry => {
    if (!isObject(value)) {
        return false;
    }
    return 'register' in value && isFunction(value.register) && 'create' in value && isFunction(value.create) && 'getMeta' in value && isFunction(value.getMeta);
};

const createPageRegistry = (): PageRegistry => new PageRegistry();

const getPageRegistry = (): PageRegistry => {
    const candidate = resolveKernelService(PAGE_REGISTRY_SERVICE_ID);
    if (!isPageRegistry(candidate)) {
        throw new Error(`${PAGE_REGISTRY_SERVICE_ID} is not registered or invalid`);
    }
    return candidate;
};

export { PageRegistry, createPageRegistry, getPageRegistry, PAGE_REGISTRY_SERVICE_ID };

export type { PageConstructor, PageMeta, PageOptions };
