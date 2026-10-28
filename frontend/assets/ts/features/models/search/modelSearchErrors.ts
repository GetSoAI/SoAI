/* SoAI - Models feature remote model search errors [frontend/assets/ts/features/models/search/modelSearchErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isRequestTimeoutError } from '@core/apiError.ts';
import { extractErrorCode } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';

const REMOTE_MODEL_SEARCH_TIMEOUT_CODE = 'remote_model_search_timeout';

const resolveModelSearchErrorMessage = (error: Error): string | null => (isRequestTimeoutError(error) || extractErrorCode(error) === REMOTE_MODEL_SEARCH_TIMEOUT_CODE ? i18n.t('models.errors.modelSearchTimeout') : null);

export { resolveModelSearchErrorMessage };
