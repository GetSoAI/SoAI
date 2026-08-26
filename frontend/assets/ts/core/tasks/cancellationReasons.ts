/* SoAI - Shared tasks cancellation reasons [frontend/assets/ts/core/tasks/cancellationReasons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

const getUserCancellationReason = (): string => i18n.t('common.cancellation.userRequested');

const getWebUiUserCancellationReason = (): string => i18n.t('common.cancellation.userRequestedViaWebUi');

export { getUserCancellationReason, getWebUiUserCancellationReason };
