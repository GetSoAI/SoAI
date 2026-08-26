/* SoAI - Notifications feature notification center [frontend/assets/ts/features/notifications/NotificationCenter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { HeaderDropdownController } from '@core/layout/header/dropdownController.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { NOTIFICATIONS_CENTER_SERVICE_ID } from '@core/notifications/protocols.ts';
import type { NotificationsListResponse } from '@core/notifications/types.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { NotificationCenterActions } from '@features/notifications/NotificationCenterActions.ts';
import { validateNotificationCenterDependencies, type NotificationCenterDependencies, type NotificationCenterHeaderApi } from '@features/notifications/NotificationCenterContracts.ts';
import { NotificationCenterDataController, type NotificationCenterSnapshotState, type NotificationCenterStreamManager } from '@features/notifications/NotificationCenterDataController.ts';
import { toggleExpandedNotificationItem } from '@features/notifications/notificationCenterExpandedDom.ts';
import { bindNotificationCenterWebSocketToasts } from '@features/notifications/notificationCenterWebSocketToasts.ts';
import { NotificationCenterView } from '@features/notifications/NotificationCenterView.ts';
import { bindNotificationCenterDomBindings, bindNotificationCenterLocalizationUpdates } from '@features/notifications/notificationCenterDomBindings.ts';
import { NotificationCenterPresentationFlow, type NotificationCenterSnapshotRenderRequest } from '@features/notifications/notificationCenterPresentationFlow.ts';
import { NotificationCenterReadSynchronizer } from '@features/notifications/NotificationCenterReadSynchronizer.ts';
import { NotificationCenterOperationController } from '@features/notifications/NotificationCenterOperationController.ts';
import { NotificationCenterAttentionOpener } from '@features/notifications/NotificationCenterAttentionOpener.ts';
import type { NotificationCenterElements } from '@features/notifications/uiTypes.ts';

class NotificationCenter extends LifecycleModel {
    readonly #dependencies: NotificationCenterDependencies;
    readonly #actions: NotificationCenterActions;
    readonly #dataController: NotificationCenterDataController;
    readonly #readSynchronizer: NotificationCenterReadSynchronizer;
    readonly #operationController: NotificationCenterOperationController;
    readonly #attentionOpener: NotificationCenterAttentionOpener;
    readonly #presentationFlow: NotificationCenterPresentationFlow;
    readonly #view: NotificationCenterView;
    readonly #dropdownController: HeaderDropdownController;

    #elements: NotificationCenterElements | null = null;
    #lastSnapshot: NotificationsListResponse | null = null;
    #lastSnapshotState: NotificationCenterSnapshotState = { status: 'loading', error: null };
    #expandedNotificationIds: Set<string> = new Set<string>();
    readonly #websocketSubscriptions = new ResourceTracker();

    badgeCount = 0;
    isVisible = false;
    isExpanded = true;

    constructor(dependencies: NotificationCenterDependencies) {
        super({ moduleId: NOTIFICATIONS_CENTER_SERVICE_ID, name: 'NotificationCenter', type: 'component' });
        validateNotificationCenterDependencies(dependencies);
        this.#dependencies = dependencies;
        this.#actions = new NotificationCenterActions(dependencies.apiClient);
        this.#dataController = new NotificationCenterDataController({
            apiClient: dependencies.apiClient,
            stream: dependencies.stream
        });
        this.#readSynchronizer = new NotificationCenterReadSynchronizer({
            actions: this.#actions,
            dataController: this.#dataController,
            requestLoadMoreIfNeeded: () => this.#loadMoreNotificationsIfNeeded()
        });
        this.#operationController = new NotificationCenterOperationController({
            actions: this.#actions,
            dataController: this.#dataController
        });
        this.#attentionOpener = new NotificationCenterAttentionOpener({
            actions: this.#actions,
            dataController: this.#dataController,
            hide: () => this.#hide()
        });
        const view = new NotificationCenterView();
        this.#view = view;
        this.#presentationFlow = new NotificationCenterPresentationFlow(view, {
            canLoadMore: () => this.#dataController.canLoadMore(),
            isLoadingMore: () => this.#dataController.isLoadingMore(),
            isMarkingRead: () => this.#readSynchronizer.isMarkingRead(),
            loadMore: () => {
                terminateHandledPromise(this.#operationController.loadMore());
            }
        });
        this.#dropdownController = new HeaderDropdownController({
            dropdownId: 'notifications',
            host: {
                on: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler)
            }
        });
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) {
            await this.destroy();
        }
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        const elements = this.#view.resolveElements();
        this.#elements = elements;
        this.#dropdownController.attach(elements.button, elements.center);
        this.#view.applyAria(elements, this.isVisible);
        this.isExpanded = true;
        this.#view.applyLocalization(elements, this.isExpanded);
        bindNotificationCenterDomBindings({
            deleteNotification: (notificationId) => {
                terminateHandledPromise(this.#operationController.deleteOne(notificationId));
            },
            elements,
            expandOrCollapse: () => this.toggleExpanded(),
            hide: () => this.hide(),
            lifecycle: { addEventListener: (target, event, handler, options) => this.lifecycleResources.addEventListener(target, event, handler, options) },
            requestLoadMoreIfNeeded: () => this.#loadMoreNotificationsIfNeeded(),
            resolveSnapshot: () => this.#lastSnapshot,
            openAttentionNotification: (record) => {
                terminateHandledPromise(this.#attentionOpener.open(record));
            },
            toggle: () => this.toggle(),
            toggleExpandedNotification: (notificationId) => this.#toggleNotificationExpanded(notificationId),
            triggerClearAll: () => {
                this.hide();
                terminateHandledPromise(this.#operationController.clearAll());
            }
        });
        bindNotificationCenterLocalizationUpdates({
            dom: this.#dependencies.dom,
            lifecycle: { addEventListener: (target, event, handler, options) => this.lifecycleResources.addEventListener(target, event, handler, options) },
            refreshRenderedLocalization: () => this.#refreshRenderedLocalization()
        });
        this.#websocketSubscriptions.track(bindNotificationCenterWebSocketToasts());
        await this.#dataController.initialize((snapshot, state) => {
            this.#lastSnapshot = snapshot;
            this.#lastSnapshotState = state;
            this.#syncRenderedSnapshot();
        });
    }

    override async onDestroy(): Promise<void> {
        if (this.isVisible) {
            this.hide();
        }
        if (this.isExpanded && this.#elements) {
            this.collapse();
        }
        this.#readSynchronizer.destroy();
        this.#operationController.destroy();
        this.#dataController.destroy();
        this.#websocketSubscriptions.cleanup();
        this.#lastSnapshot = null;
        this.#lastSnapshotState = { status: 'loading', error: null };
        this.#expandedNotificationIds.clear();
        this.#elements = null;
        this.badgeCount = 0;
        this.isExpanded = true;
        this.#dropdownController.reset();
    }

    toggle(): void {
        if (this.isVisible) {
            this.hide();
            return;
        }
        this.show();
    }

    show(): void {
        const elements = this.#requireElements();
        this.#dependencies.header.closeDropdowns({ except: 'notifications' });
        this.#view.applyAria(elements, true);
        this.#renderSnapshot(elements);
        this.#dropdownController.show();
        this.isVisible = true;
        this.#presentationFlow.syncExpandButtons(elements);
        this.#syncVisibleNotifications();
    }

    hide(): void {
        this.#hide();
    }

    #hide(): void {
        const elements = this.#requireElements();
        this.#dropdownController.hide();
        this.isVisible = false;
        this.#view.applyAria(elements, false);
        this.#expandedNotificationIds.clear();
    }

    toggleExpanded(): void {
        if (this.isExpanded) {
            this.collapse();
            return;
        }
        this.expand();
    }

    expand(): void {
        const elements = this.#requireElements();
        this.isExpanded = true;
        this.#view.setExpandedState(elements, true);
        this.#renderSnapshot(elements);
        this.#syncVisibleNotifications();
    }

    collapse(): void {
        const elements = this.#requireElements();
        this.isExpanded = false;
        this.#view.setExpandedState(elements, false);
    }

    #requireElements(): NotificationCenterElements {
        if (!this.#elements) {
            throw new Error('NotificationCenter elements not initialized');
        }
        return this.#elements;
    }

    #refreshRenderedLocalization(): void {
        const elements = this.#requireElements();
        this.#view.applyAria(elements, this.isVisible);
        this.#view.applyLocalization(elements, this.isExpanded);
        this.#renderSnapshot(elements);
        this.#syncVisibleNotifications();
    }

    #syncRenderedSnapshot(): void {
        const elements = this.#requireElements();
        this.badgeCount = this.#presentationFlow.syncSnapshot(this.#createSnapshotRenderRequest(elements));
        this.#syncVisibleNotifications();
    }

    #renderSnapshot(elements: NotificationCenterElements): void {
        this.#presentationFlow.render(this.#createSnapshotRenderRequest(elements));
    }

    #createSnapshotRenderRequest(elements: NotificationCenterElements): NotificationCenterSnapshotRenderRequest {
        return {
            elements,
            expandedNotificationIds: this.#expandedNotificationIds,
            isDropdownOpen: this.#dropdownController.isOpen(),
            isLoadingMore: this.#dataController.isLoadingMore(),
            isVisible: this.isVisible,
            snapshot: this.#lastSnapshot,
            state: this.#lastSnapshotState
        };
    }

    #syncVisibleNotifications(): void {
        this.#readSynchronizer.syncLoadedNotifications({
            isExpanded: this.isExpanded,
            isVisible: this.isVisible && this.#dropdownController.isOpen(),
            snapshot: this.#lastSnapshot
        });
        this.#loadMoreNotificationsIfNeeded();
    }

    #toggleNotificationExpanded(notificationId: string): void {
        const elements = this.#requireElements();
        toggleExpandedNotificationItem({ listElement: elements.list, expandedNotificationIds: this.#expandedNotificationIds, notificationId });
    }

    #loadMoreNotificationsIfNeeded(): void {
        this.#presentationFlow.requestLoadMoreIfNeeded({
            isDropdownOpen: this.#dropdownController.isOpen(),
            isExpanded: this.isExpanded,
            isVisible: this.isVisible,
            listElement: this.#elements ? this.#elements.list : null
        });
    }
}

export { NotificationCenter };
export type { NotificationCenterDependencies, NotificationCenterHeaderApi, NotificationCenterStreamManager };
