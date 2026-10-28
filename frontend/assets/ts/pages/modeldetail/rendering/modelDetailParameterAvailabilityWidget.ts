/* SoAI - Model detail parameter availability presentation [frontend/assets/ts/pages/modeldetail/rendering/modelDetailParameterAvailabilityWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatRelativeTime } from '@core/primitives/dateTime.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { ACTION_DISCARD_PARAMETER_CHANGES, ACTION_RETRY_PARAMETERS } from '@features/modeldetail/public.ts';
import type { ModelDetailParameterAuthority } from '@pages/modeldetail/state/ModelDetailParameterAuthorityState.ts';

const describeParameterAge = (displayedAtMs: number | null): string => (displayedAtMs === null ? i18n.t('common.unknown') : formatRelativeTime(displayedAtMs, Date.now()));

const resolveUnavailableCause = (authority: ModelDetailParameterAuthority): string => {
    switch (authority.reason) {
        case 'plugin_operation_in_progress':
            return i18n.t('models.errors.parameterSchemaBusy');
        case 'plugin_unregistered':
            return i18n.t('models.errors.parameterSchemaUnavailable');
        default:
            return i18n.t('modelDetail.parameterAvailability.failed');
    }
};

const resolveAvailabilityMessage = (authority: ModelDetailParameterAuthority, hasView: boolean): string | null => {
    if (authority.schemaBlocked) return i18n.t('modelDetail.parameterAvailability.schemaChanged');
    const age = describeParameterAge(authority.displayedAtMs);
    switch (authority.status) {
        case 'current':
            return null;
        case 'refreshing':
            return hasView ? i18n.t('modelDetail.parameterAvailability.refreshing', { age }) : i18n.t('modelDetail.parameterAvailability.loading');
        case 'stale':
            return i18n.t('modelDetail.parameterAvailability.stale', { age });
        case 'unavailable':
            return hasView ? `${resolveUnavailableCause(authority)} ${i18n.t('modelDetail.parameterAvailability.retained', { age })}` : resolveUnavailableCause(authority);
    }
};

const renderAvailabilityAction = (action: string, label: string, variant: string): TrustedHtml => uiHtml`<button type="button" class="${uiAttr(`ui-button ${variant}`)}" data-action="${uiAttr(action)}" ${renderLabelAttributes(label)}>${label}</button>`;

const renderModelDetailParameterAvailability = (pageDom: PageDom, element: HTMLElement, authority: ModelDetailParameterAuthority, hasView: boolean): void => {
    const message = resolveAvailabilityMessage(authority, hasView);
    pageDom.toggleClass(element, 'u-hidden', message === null);
    if (message === null) {
        pageDom.updateHtml(element, EMPTY_UI_HTML);
        return;
    }
    const action = authority.schemaBlocked ? renderAvailabilityAction(ACTION_DISCARD_PARAMETER_CHANGES, i18n.t('modelDetail.parameterAvailability.discard'), 'ui-variant-danger') : authority.status === 'stale' || authority.status === 'unavailable' ? renderAvailabilityAction(ACTION_RETRY_PARAMETERS, i18n.t('common.retry'), 'ui-variant-neutral') : EMPTY_UI_HTML;
    pageDom.updateHtml(element, uiHtml`<p>${message}</p>${action}`);
};

export { renderModelDetailParameterAvailability };
