/* SoAI - OAuth value normalization [frontend/assets/ts/features/settings/oauthValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { OAUTH_STATUSES, type OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import { isAllowedStringValue } from '@core/types/payloadValueReaders.ts';

const SETTINGS_OAUTH_TERMINAL_STATUSES: readonly OauthStatus[] = ['ready', 'auth_required', 'insufficient_scope', 'expired', 'error'];
const SETTINGS_OAUTH_ACTION_BLOCKED_STATUSES: readonly OauthStatus[] = ['auth_required', 'insufficient_scope', 'expired', 'error'];
const SETTINGS_OAUTH_WARNING_STATUSES: readonly OauthStatus[] = ['auth_required', 'insufficient_scope', 'expired'];

const isOauthStatusIn = (value: string | null | undefined, statuses: readonly OauthStatus[]): boolean => isAllowedStringValue(value, statuses);

const isTerminalSettingsOauthStatus = (value: OauthStatus | null): boolean => value !== null && isOauthStatusIn(value, SETTINGS_OAUTH_TERMINAL_STATUSES);
const isSettingsOauthActionBlockedStatus = (value: string | null | undefined): boolean => isOauthStatusIn(value, SETTINGS_OAUTH_ACTION_BLOCKED_STATUSES);
const isSettingsOauthWarningStatus = (value: string | null | undefined): boolean => isOauthStatusIn(value, SETTINGS_OAUTH_WARNING_STATUSES);
const isSettingsOauthStatus = (value: string | null | undefined): value is OauthStatus => isOauthStatusIn(value, OAUTH_STATUSES);

export { isSettingsOauthActionBlockedStatus, isSettingsOauthStatus, isSettingsOauthWarningStatus, isTerminalSettingsOauthStatus };
