/* SoAI - Frontend WebUI external account endpoints [frontend/assets/ts/core/api/endpoints/webuiExternalAccounts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeAccountList, decodeCalendarAccount, decodeExternalAccountAction, decodeExternalAccountOauthStatus, decodeMailAccount, type CalendarAccountEntry, type CalendarAccountWriteRequest, type ExternalAccountActionResponse, type ExternalAccountType, type MailAccountEntry, type MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { serializeCalendarAccountWriteRequest, serializeMailAccountWriteRequest } from '@core/api/contracts/externalAccountRequestSerialization.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface ExternalAccountsEndpoints<Account, WriteRequest> {
    list(): Promise<Account[]>;
    create(payload: WriteRequest): Promise<Account>;
    update(accountId: string, payload: WriteRequest): Promise<Account>;
    delete(accountId: string): Promise<ExternalAccountActionResponse>;
    test(accountId: string): Promise<ExternalAccountActionResponse>;
    sync(accountId: string): Promise<ExternalAccountActionResponse>;
    oauth: {
        start(accountId: string): Promise<ExternalAccountActionResponse>;
        status(accountId: string): Promise<OauthStatus>;
        clear(accountId: string): Promise<ExternalAccountActionResponse>;
    };
}

interface WebuiExternalAccountsEndpoints {
    mail: { accounts: ExternalAccountsEndpoints<MailAccountEntry, MailAccountWriteRequest> };
    calendar: { accounts: ExternalAccountsEndpoints<CalendarAccountEntry, CalendarAccountWriteRequest> };
}

const createAccountsEndpoints = <Account, WriteRequest>(api: ApiClientContext, basePath: string, type: ExternalAccountType, decodeAccount: (value: ApiResponsePayload) => Account, serializeRequest: (request: WriteRequest) => JsonObject): ExternalAccountsEndpoints<Account, WriteRequest> => ({
    list: async (): Promise<Account[]> => decodeAccountList(await api.get(basePath), type, decodeAccount),
    create: async (payload): Promise<Account> => decodeAccount(await api.post(basePath, serializeRequest(payload))),
    update: async (accountId, payload): Promise<Account> => decodeAccount(await api.patch(`${basePath}/${api.encodePathSegment(accountId)}`, serializeRequest(payload))),
    delete: async (accountId): Promise<ExternalAccountActionResponse> => decodeExternalAccountAction(await api.delete(`${basePath}/${api.encodePathSegment(accountId)}`), type),
    test: async (accountId): Promise<ExternalAccountActionResponse> => decodeExternalAccountAction(await api.post(`${basePath}/${api.encodePathSegment(accountId)}/test`), type),
    sync: async (accountId): Promise<ExternalAccountActionResponse> => decodeExternalAccountAction(await api.post(`${basePath}/${api.encodePathSegment(accountId)}/sync`, {}), type),
    oauth: {
        start: async (accountId): Promise<ExternalAccountActionResponse> => decodeExternalAccountAction(await api.post(`${basePath}/${api.encodePathSegment(accountId)}/oauth/start`), type),
        status: async (accountId): Promise<OauthStatus> => decodeExternalAccountOauthStatus(await api.get(`${basePath}/${api.encodePathSegment(accountId)}/oauth/status`), type),
        clear: async (accountId): Promise<ExternalAccountActionResponse> => decodeExternalAccountAction(await api.post(`${basePath}/${api.encodePathSegment(accountId)}/oauth/clear`), type)
    }
});

const createWebuiExternalAccountsEndpoints = (api: ApiClientContext): WebuiExternalAccountsEndpoints => ({
    mail: { accounts: createAccountsEndpoints<MailAccountEntry, MailAccountWriteRequest>(api, '/api/v1/webui/users/me/mail/accounts', 'mail', decodeMailAccount, serializeMailAccountWriteRequest) },
    calendar: { accounts: createAccountsEndpoints<CalendarAccountEntry, CalendarAccountWriteRequest>(api, '/api/v1/webui/users/me/calendar/accounts', 'calendar', decodeCalendarAccount, serializeCalendarAccountWriteRequest) }
});

export { createWebuiExternalAccountsEndpoints };
export type { ExternalAccountsEndpoints, WebuiExternalAccountsEndpoints };
