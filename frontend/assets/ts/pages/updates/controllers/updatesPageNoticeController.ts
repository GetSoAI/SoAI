/* SoAI - Updates page control layer notice controller [frontend/assets/ts/pages/updates/controllers/updatesPageNoticeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setUpdatesPageNotice } from '@pages/updates/controllers/UpdatesSystemStatusView.ts';
import type { UpdatesInstallOutcome, UpdatesOperationOutcome } from '@core/edition/updatesContribution.ts';
import type { UpdatesPageNoticeTone, UpdatesUiRefs } from '@pages/updates/types.ts';

type NoticeHost = {
    updateText: (element: Element, text: string) => void;
    toggleHidden: (element: Element, hidden: boolean) => void;
};

type NoticeUiRefs = Pick<UpdatesUiRefs, 'pageNotice' | 'pageNoticeIndicator' | 'pageNoticeHeading' | 'pageNoticeDetail'>;
type NoticeOutcomeSource = 'application' | 'product';
type NoticeOutcomeEntry = {
    label: string;
    outcome: UpdatesOperationOutcome;
    source: NoticeOutcomeSource;
};

type UpdatesCheckNotification = {
    message: string;
    type: 'error' | 'refresh';
};

const setUpdatesNotice = (host: NoticeHost, ui: NoticeUiRefs, tone: UpdatesPageNoticeTone, heading: string, detail = ''): void => {
    setUpdatesPageNotice(host, ui, { tone, heading, detail });
};

const normalizeNoticeMessage = (message: string, fallback: string): string => {
    const trimmed = message.trim();
    const normalized = trimmed.toLocaleLowerCase();
    if (!trimmed || normalized === 'update check failed.' || normalized === i18n.t('updates.notifications.checkFailed').toLocaleLowerCase()) {
        return fallback;
    }
    return trimmed;
};

const formatFailureDetail = (label: string, outcome: UpdatesOperationOutcome): string => `${label}: ${normalizeNoticeMessage(outcome.message, i18n.t('updates.errors.noDetailedError'))}`;

const formatSuccessDetail = (source: 'application' | 'product', label: string, outcome: UpdatesOperationOutcome): string => {
    if (outcome.type === 'updatesFound') {
        return `${label}: ${source === 'application' ? i18n.t('updates.status.applicationUpdatesFound') : i18n.t('updates.status.productUpdatesFound', { count: outcome.updatesCount })}`;
    }
    if (outcome.type === 'noUpdates') {
        return `${label}: ${source === 'application' ? i18n.t('updates.status.applicationNoUpdatesFound') : i18n.t('updates.status.productNoUpdatesFound')}`;
    }
    return '';
};

const applyInitialUpdatesNotice = (host: NoticeHost, ui: NoticeUiRefs): void => {
    setUpdatesNotice(host, ui, 'grey', i18n.t('updates.status.idle'));
};

const applyCheckingUpdatesNotice = (host: NoticeHost, ui: NoticeUiRefs): void => {
    setUpdatesNotice(host, ui, 'blue', i18n.t('updates.status.fetchingAll'));
};

const applyOperationTimeoutNotice = (host: NoticeHost, ui: NoticeUiRefs): void => {
    setUpdatesNotice(host, ui, 'red', i18n.t('updates.errors.operationTimeout'));
};

const applyInstallStartedNotice = (host: NoticeHost, ui: NoticeUiRefs): void => {
    setUpdatesNotice(host, ui, 'orange', i18n.t('updates.status.installing'));
};

const applyInstallOutcomeNotice = (host: NoticeHost, ui: NoticeUiRefs, outcome: UpdatesInstallOutcome): void => {
    if (outcome.type === 'error') {
        setUpdatesNotice(host, ui, 'red', outcome.message);
    }
    if (outcome.type === 'completed') {
        setUpdatesNotice(host, ui, 'green', outcome.message);
    }
    if (outcome.type === 'started') {
        setUpdatesNotice(host, ui, 'orange', outcome.message);
    }
};

const resolveCheckNotice = (application: UpdatesOperationOutcome, product: UpdatesOperationOutcome): { tone: UpdatesPageNoticeTone; heading: string; detail: string } => {
    const applicationLabel = i18n.t('updates.status.applicationCheckLabel');
    const productLabel = i18n.t('updates.status.productCheckLabel');
    const entries: readonly NoticeOutcomeEntry[] = [
        { label: applicationLabel, outcome: application, source: 'application' },
        { label: productLabel, outcome: product, source: 'product' }
    ];
    const failures = entries.filter((entry) => entry.outcome.type === 'error');
    if (failures.length > 0) {
        const successes = entries.filter((entry) => entry.outcome.type === 'updatesFound' || entry.outcome.type === 'noUpdates');
        const details = [...failures.map((entry) => formatFailureDetail(entry.label, entry.outcome)), ...successes.map((entry) => formatSuccessDetail(entry.source, entry.label, entry.outcome)).filter(Boolean)];
        return {
            tone: 'red',
            heading: failures.length === 1 && successes.length > 0 ? i18n.t('updates.status.someChecksFailed') : i18n.t('updates.notifications.checkFailed'),
            detail: details.join(' ')
        };
    }
    const applicationUpdates = application.type === 'updatesFound';
    const productUpdates = product.type === 'updatesFound';
    if (applicationUpdates && productUpdates) {
        return { tone: 'blue', heading: i18n.t('updates.status.applicationAndProductUpdatesFound'), detail: '' };
    }
    if (applicationUpdates) {
        return { tone: 'blue', heading: i18n.t('updates.status.applicationUpdatesFound'), detail: '' };
    }
    if (productUpdates) {
        return { tone: 'blue', heading: i18n.t('updates.status.productUpdatesFound', { count: product.updatesCount }), detail: '' };
    }
    return { tone: 'green', heading: i18n.t('updates.status.noUpdatesFound'), detail: '' };
};

const applyCheckOutcomeNotice = (host: NoticeHost, ui: NoticeUiRefs, application: UpdatesOperationOutcome, product: UpdatesOperationOutcome): void => {
    const notice = resolveCheckNotice(application, product);
    setUpdatesNotice(host, ui, notice.tone, notice.heading, notice.detail);
};

const resolveUpdatesCheckNotification = (application: UpdatesOperationOutcome, product: UpdatesOperationOutcome): UpdatesCheckNotification | null => {
    if (application.type === 'error' || product.type === 'error') {
        return { message: i18n.t('updates.notifications.checkFailed'), type: 'error' };
    }
    const hasCompletedCheck = application.type === 'updatesFound' || application.type === 'noUpdates' || product.type === 'updatesFound' || product.type === 'noUpdates';
    if (!hasCompletedCheck) {
        return null;
    }
    return { message: i18n.t('common.notifications.refreshCompleted'), type: 'refresh' };
};

export { applyCheckOutcomeNotice, applyCheckingUpdatesNotice, applyInitialUpdatesNotice, applyInstallOutcomeNotice, applyInstallStartedNotice, applyOperationTimeoutNotice, resolveUpdatesCheckNotification };
