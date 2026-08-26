/* SoAI - Settings page users manager validation [frontend/assets/ts/pages/settings/controllers/usersmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredEnumValue } from '@core/types/payloadValueReaders.ts';
import type { UserRole } from '@pages/settings/controllers/usersmanager/types.ts';

const USER_ROLE_VALUES: readonly UserRole[] = ['admin', 'user'];

const parseUserRole = (value: string): UserRole => {
    return readRequiredEnumValue(value, 'User role', USER_ROLE_VALUES);
};

export { parseUserRole };
