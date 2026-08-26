/* SoAI - Settings feature filters [frontend/assets/ts/features/settings/apikeys/filters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiKey } from '@features/settings/apikeys/types.ts';

const filterActiveApiKeys = (keys: readonly ApiKey[]): ApiKey[] => keys.filter((key) => !key.revoked);

const hasRevokedApiKeys = (keys: readonly ApiKey[]): boolean => keys.some((key) => key.revoked);

const filterVisibleApiKeys = (keys: readonly ApiKey[], showRevoked: boolean): ApiKey[] => (showRevoked ? [...keys] : filterActiveApiKeys(keys));

export { filterActiveApiKeys, filterVisibleApiKeys, hasRevokedApiKeys };
