/* SoAI - Plugins page effects [frontend/assets/ts/pages/plugins/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LoadPluginsPageDataDependencies {
    cardController: { showLoading(): void; setDataInitialized(): void } | null;
    runWithBoundary<T>(scope: string, task: () => Promise<T>): Promise<T>;
    withCollectionLoading(task: () => Promise<void>, options: { loadingText: string; onSuccess: () => Promise<void> }): Promise<void>;
    ensureCollectionStream(): Promise<void>;
    getLoadingText(): string;
    ensureDataSubscriptions(): Promise<void>;
    loadInitialData(): Promise<void>;
    updateStats(): void;
    beginRecentItemsSync(): number;
    armRecentItems(syncSequence: number): void;
}

const loadPluginsPageData = async (dependencies: LoadPluginsPageDataDependencies): Promise<void> => {
    const recentItemsSync = dependencies.beginRecentItemsSync();
    dependencies.cardController?.showLoading();
    await dependencies.runWithBoundary('plugins:loadData', async (): Promise<void> => {
        await dependencies.withCollectionLoading(
            async (): Promise<void> => {
                await Promise.all([dependencies.ensureCollectionStream(), dependencies.loadInitialData()]);
            },
            {
                loadingText: dependencies.getLoadingText(),
                onSuccess: async (): Promise<void> => {
                    await dependencies.ensureDataSubscriptions();
                    dependencies.cardController?.setDataInitialized();
                    dependencies.updateStats();
                    dependencies.armRecentItems(recentItemsSync);
                }
            }
        );
    });
};

export { loadPluginsPageData };
export type { LoadPluginsPageDataDependencies };
