/* SoAI - Shared routing router dependencies [frontend/assets/ts/core/routing/router/routerDependencies.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComponentMeta } from '@core/componentsupport/types.ts';
import type { PageInstance, PageRegistry } from '@core/pagehost/types.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageHostInstance } from '@core/pageoutlet/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { DisposableResource, EventTargetInput } from '@core/resourcetracker/types.ts';
import type { ElementOptions, ReplaceContentOptions } from '@core/dom/types.ts';

interface SidebarServiceContract {
    setActiveByPage: (page: string) => void;
    initialized?: boolean;
}

interface DomService {
    getBody: () => HTMLElement;
    getDocument: () => Document;
    resolve: (selector: string, context?: Element | Document | null) => Element | null;
    resolveAll: (selector: string, context?: Element | Document | null) => Element[];
    setStyle: (element: Element, property: string, value: string | null) => void;
    create: (tag: string, attrs?: ElementOptions) => Element;
    createFragmentFromNodes: (children?: Node | NodeList | string | null | undefined) => DocumentFragment;
    replaceContent: (container: Element, content: DocumentFragment | string, options?: ReplaceContentOptions) => void;
}

interface StorageService {
    setRedirectAfterLogin: (path: string) => void;
    getRedirectAfterLogin: () => string | null;
    clearRedirectAfterLogin: () => void;
    isWizardCompletionPending: () => boolean;
    isWizardCompleted: () => boolean;
    getDefaultPage: () => string | null;
}

interface AuthService {
    isAuthenticated: boolean;
    isAdmin: () => boolean;
    checkWizardStatus: () => Promise<boolean>;
    onLogin: (callback: () => void | Promise<void>) => (() => void) | void;
    onLogout: (callback: () => void | Promise<void>) => (() => void) | void;
}

interface ApiService {
    webui: {
        terminal: {
            policy: () => Promise<{
                canAccessTerminal: boolean;
                adminCount: number;
                policyRevision: string;
            }>;
        };
    };
}

interface StreamManagerService {
    ensureReady: (options: { allowDiscovery: boolean; signal?: AbortSignal | undefined }) => Promise<void>;
    ensureResourceStarted: (name: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined }) => Promise<JsonValue | null | undefined>;
}

interface StateService {
    section: {
        cleanup: () => void;
        initialize: () => void;
    };
    setTabState: (key: string, value: JsonValue | null | undefined) => void;
}

interface CleanupManagerService {
    cleanupAll: () => Promise<void>;
}

interface ErrorHandlerService {
    error: (module: string, message: string, error?: Error) => void;
    warn: (module: string, message: string, error?: Error) => void;
    debug: (module: string, message: string, data?: Error | JsonValue | null | undefined | null) => void;
    info: (module: string, message: string, data?: Error | JsonValue | null | undefined | null) => void;
}

interface PageOutletService {
    setContainer: (container: HTMLElement | string) => PageOutletService;
    getContainer: () => HTMLElement;
    getPageHost: () => PageHostInstance;
    destroyCurrent: (options?: { force?: boolean }) => Promise<void>;
    destroy?: () => Promise<void>;
    render: (options: { component: string; parameters: JsonObject; beforePrepare?: (() => void | Promise<void>) | Promise<void> | null | undefined; beforeCommit?: (() => void | Promise<void>) | Promise<void> | null | undefined; commitNavigation?: (() => void) | undefined; signal?: AbortSignal | undefined }) => Promise<{ name: string; instance: PageInstance } | null>;
    cancelActive: (reason?: string) => void;
    waitForCommit: () => Promise<void>;
    setSkeleton: (route: string) => void;
    getState?: (() => string) | undefined;
}

type PageOutletConstructor = new (options: { emitEvent: RouterEventEmitter; onPreservedPageFailure: () => void; onRetry: () => void; pageRegistry: PageRegistry }) => PageOutletService;

interface ResourceTrackerClass {
    new (): ResourceTrackerInstance;
}

interface ResourceTrackerInstance {
    addEventListener: (target: EventTargetInput, event: string, handler: (event: Event) => void, options?: AddEventListenerOptions | boolean) => () => void;
    track?: <T extends DisposableResource>(disposable: T, cleanup?: ((disposable: T) => void) | undefined) => T;
    cleanup: () => void;
}

interface ErrorBoundaryClass {
    new (name: string): ErrorBoundaryInstance;
}

interface ErrorBoundaryInstance {
    execute: <T>(functionValue: () => Promise<T> | T, label: string) => Promise<T>;
}

type RouterEventEmitter = (stage: string, data?: Record<string, JsonValue | null | undefined>, severity?: string) => void;

interface RouterDependencies {
    dom: DomService;
    storage: StorageService;
    auth: AuthService;
    api: ApiService;
    streamManager: StreamManagerService;
    state: StateService;
    cleanupManager: CleanupManagerService;
    ResourceTracker: ResourceTrackerClass;
    errorHandler: ErrorHandlerService;
    PageOutlet: PageOutletConstructor;
    ErrorBoundary: ErrorBoundaryClass;
    modalPresenter: ModalPresenterApi;
    componentRegistry: Map<string, ComponentMeta>;
    pageRegistry: PageRegistry;
    getSidebarService: () => SidebarServiceContract | null;
}

export type { SidebarServiceContract, ApiService, AuthService, CleanupManagerService, DomService, ErrorBoundaryClass, ErrorBoundaryInstance, ErrorHandlerService, PageOutletService, ResourceTrackerClass, ResourceTrackerInstance, RouterDependencies, RouterEventEmitter, StateService, StorageService, StreamManagerService };
