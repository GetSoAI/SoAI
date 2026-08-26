/* SoAI - Settings page host bindings [frontend/assets/ts/pages/settings/controllers/page/hostBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';

const hasSearchQuery = (page: SettingsRuntimeContext): boolean => Boolean(page.controls.getSearchQuery()?.trim());

const bindRunWithBoundary =
    <T>(page: SettingsRuntimeContext): ((name: string, task: () => Promise<T> | T) => Promise<T>) =>
    (name, task) =>
        page.owners.pageLifecycle.run(name, task);

const buildBaseHostBindings = (
    page: SettingsRuntimeContext,
    callbacks: SettingsManagerCallbacks
): {
    pageDom: SettingsRuntimeContext['owners']['pageDom'];
    pageResources: SettingsRuntimeContext['owners']['pageResources'];
    feedback: SettingsRuntimeContext['owners']['feedback'];
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
    filterSettings: () => void;
    confirmAndExecute: SettingsManagerCallbacks['confirmAndExecute'];
} => ({
    pageDom: page.owners.pageDom,
    pageResources: page.owners.pageResources,
    feedback: page.owners.feedback,
    runWithBoundary: bindRunWithBoundary(page),
    filterSettings: callbacks.filterSettings,
    confirmAndExecute: callbacks.confirmAndExecute
});

const buildAdminHostBindings = (
    page: SettingsRuntimeContext,
    callbacks: SettingsManagerCallbacks
): ReturnType<typeof buildBaseHostBindings> & {
    isAdmin: () => boolean;
    hasSearchQuery: () => boolean;
} => ({
    ...buildBaseHostBindings(page, callbacks),
    isAdmin: (): boolean => page.owners.auth.isAdmin(),
    hasSearchQuery: (): boolean => hasSearchQuery(page)
});

export { buildAdminHostBindings, buildBaseHostBindings, hasSearchQuery };
