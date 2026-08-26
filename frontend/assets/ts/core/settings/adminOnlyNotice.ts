/* SoAI - Shared settings admin only notice [frontend/assets/ts/core/settings/adminOnlyNotice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';

const renderAdminOnlyNotice = (message: string): TrustedHtml => uiHtml`<div class="settings-admin-only-notice">${message}</div>`;

export { renderAdminOnlyNotice };
