/* SoAI - Frontend shared OAuth wire contracts [frontend/assets/ts/core/api/contracts/oauthContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredEnumValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type OauthStatus = 'none' | 'ready' | 'auth_required' | 'insufficient_scope' | 'expired' | 'error';

const OAUTH_STATUSES: readonly OauthStatus[] = ['none', 'ready', 'auth_required', 'insufficient_scope', 'expired', 'error'];

const decodeOauthStatus = (value: JsonValue | undefined, label: string): OauthStatus => readRequiredEnumValue(value, label, OAUTH_STATUSES);

export { decodeOauthStatus, OAUTH_STATUSES };
export type { OauthStatus };
