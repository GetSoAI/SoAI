/* SoAI - Settings security tab notify badge controller [frontend/assets/ts/pages/settings/controllers/page/securityTabBadgeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const SECURITY_TAB_ID = 'security';
const SECURITY_NOTIFY_BADGE_SELECTOR = '#security-notify';
const SECURITY_NOTIFY_BADGE_VARIANT = 'tab-notify-badge--security';

const resolveSecurityFindingCount = (state: SettingsPageState): number => {
    const audit = state.securityAudit;
    if (audit === null || audit.secure) {
        return 0;
    }
    return audit.issueCount;
};

const applySecurityNotifyBadgeVariant = (page: SettingsRuntimeContext, active: boolean): void => {
    const badge = page.owners.pageDom.optional(SECURITY_NOTIFY_BADGE_SELECTOR);
    if (!badge) {
        return;
    }
    badge.classList.toggle(SECURITY_NOTIFY_BADGE_VARIANT, active);
};

const updateSecurityTabNotifyBadge = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    page.owners.layout.getTabs()?.updateTabNotifyBadge(SECURITY_TAB_ID, resolveSecurityFindingCount(state));
    applySecurityNotifyBadgeVariant(page, resolveSecurityFindingCount(state) > 0);
};

export { SECURITY_TAB_ID, applySecurityNotifyBadgeVariant, resolveSecurityFindingCount, updateSecurityTabNotifyBadge };
