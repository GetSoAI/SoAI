/* SoAI - Settings feature apikeys constants [frontend/assets/ts/features/settings/apikeys/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const API_KEYS_ACTION_CREATE = 'settings.apiKeys.create';
const API_KEYS_ACTION_DELETE_ALL = 'settings.apiKeys.deleteAll';
const API_KEYS_ACTION_MANAGE_QUOTA = 'settings.apiKeys.manageQuota';
const API_KEYS_ACTION_REVOKE = 'settings.apiKeys.revoke';
const API_KEYS_ACTION_ROTATE = 'settings.apiKeys.rotate';
const API_KEYS_ACTION_DELETE = 'settings.apiKeys.delete';

type ApiKeysActionId = typeof API_KEYS_ACTION_CREATE | typeof API_KEYS_ACTION_DELETE_ALL | typeof API_KEYS_ACTION_MANAGE_QUOTA | typeof API_KEYS_ACTION_REVOKE | typeof API_KEYS_ACTION_ROTATE | typeof API_KEYS_ACTION_DELETE;

const API_KEYS_CREATE_LABEL_MODAL_ID = 'settings-api-key-create-label-modal';
const API_KEYS_CREATE_EXPIRY_MODAL_ID = 'settings-api-key-create-expiry-modal';
const API_KEYS_SECRET_MODAL_ID = 'settings-api-key-secret-modal';
const API_KEYS_QUOTA_MODAL_ID = 'settings-api-key-quota-modal';

const { guard: isApiKeysActionId } = createActionIdSet(API_KEYS_ACTION_CREATE, API_KEYS_ACTION_DELETE_ALL, API_KEYS_ACTION_MANAGE_QUOTA, API_KEYS_ACTION_REVOKE, API_KEYS_ACTION_ROTATE, API_KEYS_ACTION_DELETE);

export { API_KEYS_ACTION_CREATE, API_KEYS_ACTION_DELETE_ALL, API_KEYS_ACTION_MANAGE_QUOTA, API_KEYS_ACTION_REVOKE, API_KEYS_ACTION_ROTATE, API_KEYS_ACTION_DELETE, API_KEYS_CREATE_LABEL_MODAL_ID, API_KEYS_CREATE_EXPIRY_MODAL_ID, API_KEYS_SECRET_MODAL_ID, API_KEYS_QUOTA_MODAL_ID, isApiKeysActionId };
export type { ApiKeysActionId };
