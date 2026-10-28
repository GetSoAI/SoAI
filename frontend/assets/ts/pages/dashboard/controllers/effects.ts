/* SoAI - Dashboard page controllers effects [frontend/assets/ts/pages/dashboard/controllers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { DASHBOARD_SECTION_RENDER_ORDER } from '@pages/dashboard/contracts/constants.ts';
import { applyDashboardLiveDataUpdate, type DashboardLiveDataContext, type DashboardLiveDataKey, type DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';

interface KeyedListRow<T> {
    key: string;
    signature: string;
    value: T;
}

interface SyncKeyedListOptions<T> {
    content: HTMLElement;
    listClassName: string;
    rows: readonly KeyedListRow<T>[];
    createList: () => HTMLElement;
    createRow: (value: T, index: number) => HTMLElement;
}

interface DashboardSubscriptionSpec {
    resource: string;
    key: DashboardLiveDataKey;
}

const findDirectChildByClass = (content: HTMLElement, className: string): HTMLElement | null => {
    for (const child of Array.from(content.children)) {
        if (child instanceof HTMLElement && child.classList.contains(className)) {
            return child;
        }
    }
    return null;
};

const getKeyedRowMap = (list: HTMLElement): Map<string, HTMLElement> => {
    const keyedRows = new Map<string, HTMLElement>();
    for (const child of Array.from(list.children)) {
        if (!(child instanceof HTMLElement)) continue;
        const key = child.dataset['dashboardRowKey'];
        if (typeof key === 'string') {
            keyedRows.set(key, child);
        }
    }
    return keyedRows;
};

const syncKeyedList = <T>({ content, listClassName, rows, createList, createRow }: SyncKeyedListOptions<T>): HTMLElement => {
    let list = findDirectChildByClass(content, listClassName);
    if (!list) {
        list = createList();
        content.replaceChildren(list);
    }

    const nextKeys = new Set(rows.map((row) => row.key));
    const keyedRows = getKeyedRowMap(list);
    for (const [key, existing] of keyedRows) {
        if (!nextKeys.has(key)) {
            removeWithPresence(existing);
            keyedRows.delete(key);
        }
    }

    const previousOrder = [...keyedRows.keys()];
    const orderedRows = [...rows].sort((first, second) => {
        const firstIndex = previousOrder.indexOf(first.key);
        const secondIndex = previousOrder.indexOf(second.key);
        return (firstIndex < 0 ? previousOrder.length : firstIndex) - (secondIndex < 0 ? previousOrder.length : secondIndex);
    });
    let reference: ChildNode | null = list.firstChild;
    for (let index = 0; index < orderedRows.length; index += 1) {
        const row = orderedRows[index];
        if (!row) {
            throw new Error('Dashboard keyed list row missing at render index');
        }
        const existing = keyedRows.get(row.key);
        const next = createRow(row.value, index);
        const element = existing ?? next;
        if (existing && existing.dataset['dashboardRowSignature'] !== row.signature) {
            existing.className = next.className;
            reconcileChildNodes(existing, Array.from(next.childNodes));
        }
        element.dataset['dashboardRowKey'] = row.key;
        element.dataset['dashboardRowSignature'] = row.signature;
        insertWithPresence(list, element, reference);
        if (element !== reference) list.insertBefore(element, reference);
        reference = element.nextSibling;
    }

    return list;
};

interface DashboardSubscriptionSetupDependencies {
    subscriptions: ReadonlyArray<DashboardSubscriptionSpec>;
    subscribeToData: (resource: string, handler: (payload: JsonValue) => void) => () => void;
    registerDashboardSubscription: (subscription: () => void) => void;
    handleLiveData: (type: DashboardLiveDataKey, payload: JsonValue) => void;
}

const setupDashboardSubscriptions = (dependencies: DashboardSubscriptionSetupDependencies): void => {
    for (const { resource, key } of dependencies.subscriptions) {
        const unsubscribe = dependencies.subscribeToData(resource, (payload: JsonValue): void => {
            void dependencies.handleLiveData(key, payload);
        });
        if (typeof unsubscribe !== 'function') {
            throw new Error(`Dashboard subscription for "${resource}" must return an unsubscribe function`);
        }
        dependencies.registerDashboardSubscription(unsubscribe);
    }
};

interface DashboardMainStateMonitoringDependencies {
    subscribeMainState: (callback: (state: string) => void) => () => void;
    updateMainStateIndicator: (state: string) => void;
}

const setupDashboardMainStateMonitoring = (dependencies: DashboardMainStateMonitoringDependencies): (() => void) => {
    return dependencies.subscribeMainState((state: string): void => {
        dependencies.updateMainStateIndicator(state);
    });
};

interface DashboardLiveDataUpdateDependencies {
    liveDataContext: DashboardLiveDataContext;
    type: DashboardLiveDataKey;
    payload: JsonValue;
    queueRender: (sectionId: DashboardSectionId) => void;
    isDestroyed: () => boolean;
}

const handleDashboardLiveDataUpdate = (dependencies: DashboardLiveDataUpdateDependencies): void => {
    const updatedSections = applyDashboardLiveDataUpdate(dependencies.liveDataContext, dependencies.type, dependencies.payload);
    if (!updatedSections.length || dependencies.isDestroyed()) {
        return;
    }
    for (const sectionId of updatedSections) {
        dependencies.queueRender(sectionId);
    }
};

interface DashboardSectionRenderQueueDependencies {
    renderSection: (sectionId: DashboardSectionId) => Promise<void>;
    isDestroyed: () => boolean;
}

interface DashboardSectionRenderQueue {
    queueSectionRender(sectionId: DashboardSectionId): void;
    setSectionsReady(isReady: boolean, signal?: AbortSignal | null): Promise<void>;
    clear(): void;
}

const createDashboardSectionRenderQueue = (dependencies: DashboardSectionRenderQueueDependencies): DashboardSectionRenderQueue => {
    const sectionOrder = DASHBOARD_SECTION_RENDER_ORDER;

    let sectionsReady = false;
    const pendingSections = new Set<DashboardSectionId>();

    const renderQueue = new AnimationFrameRenderQueue<ReadonlySet<DashboardSectionId>>({
        label: 'DashboardSectionRenderQueue',
        required: true,
        isDisposed: dependencies.isDestroyed,
        merge: (previous, next): ReadonlySet<DashboardSectionId> => new Set<DashboardSectionId>([...(previous ?? []), ...next]),
        render: async (pending): Promise<void> => {
            if (!sectionsReady || dependencies.isDestroyed()) {
                return;
            }
            const unordered = new Set(pending);
            for (const sectionId of sectionOrder) {
                if (!unordered.has(sectionId)) {
                    continue;
                }
                if (!sectionsReady || dependencies.isDestroyed()) return;
                await dependencies.renderSection(sectionId);
                unordered.delete(sectionId);
            }
            for (const sectionId of unordered) {
                if (!sectionsReady || dependencies.isDestroyed()) return;
                await dependencies.renderSection(sectionId);
            }
        }
    });

    return {
        queueSectionRender(sectionId: DashboardSectionId): void {
            if (dependencies.isDestroyed()) {
                return;
            }
            if (!sectionsReady) {
                pendingSections.add(sectionId);
                return;
            }
            renderQueue.schedule(new Set([sectionId]));
        },
        async setSectionsReady(isReady: boolean, signal: AbortSignal | null = null): Promise<void> {
            sectionsReady = isReady;
            if (!isReady) {
                return;
            }
            for (const sectionId of pendingSections) {
                renderQueue.schedule(new Set([sectionId]));
            }
            pendingSections.clear();
            await renderQueue.waitForIdle(signal);
        },
        clear(): void {
            sectionsReady = false;
            pendingSections.clear();
            renderQueue.cancel();
        }
    };
};

export { createDashboardSectionRenderQueue, handleDashboardLiveDataUpdate, setupDashboardMainStateMonitoring, setupDashboardSubscriptions, syncKeyedList };
export type { DashboardSectionRenderQueue, KeyedListRow };
