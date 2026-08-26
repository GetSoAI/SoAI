/* SoAI - Dashboard page widgets logs labels widget [frontend/assets/ts/pages/dashboard/widgets/logs/LogsLabelsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

const formatLogsAutoScrollLabel = (enabled: boolean): string => {
    const stateLabel = enabled ? i18n.t('dashboard.sections.logs.autoScrollOn') : i18n.t('dashboard.sections.logs.autoScrollOff');
    return `${i18n.t('dashboard.sections.logs.autoScroll')}: ${stateLabel}`;
};

export { formatLogsAutoScrollLabel };
