/* SoAI - WebUI Messaging account endpoints [frontend/assets/ts/core/api/endpoints/webuiMessagingAccounts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeMessagingAccount, decodeMessagingAccounts, decodeMessagingMcpCatalog, type MessagingAccount, type MessagingAccountCreate, type MessagingAccountUpdate } from '@core/api/contracts/messagingAccountContracts.ts';
import { serializeMessagingAccountCreate, serializeMessagingAccountUpdate } from '@core/api/contracts/messagingAccountSerialization.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { McpFormCatalog } from '@core/mcp/configTypes.ts';

interface WebuiMessagingAccountEndpoints {
    list(): Promise<MessagingAccount[]>;
    get(accountId: string): Promise<MessagingAccount>;
    create(account: MessagingAccountCreate): Promise<MessagingAccount>;
    update(accountId: string, account: MessagingAccountUpdate): Promise<MessagingAccount>;
    delete(accountId: string, expectedRevision: number): Promise<void>;
    listMcpTools(): Promise<McpFormCatalog>;
}

const createWebuiMessagingAccountEndpoints = (api: ApiClientContext): WebuiMessagingAccountEndpoints => {
    const path = (accountId: string): string => `/api/v1/webui/messaging/accounts/${api.encodePathSegment(accountId)}`;
    return {
        list: async (): Promise<MessagingAccount[]> => decodeMessagingAccounts(await api.get('/api/v1/webui/messaging/accounts')),
        get: async (accountId): Promise<MessagingAccount> => decodeMessagingAccount(await api.get(path(accountId))),
        create: async (account): Promise<MessagingAccount> => decodeMessagingAccount(await api.post('/api/v1/webui/messaging/accounts', serializeMessagingAccountCreate(account))),
        update: async (accountId, account): Promise<MessagingAccount> => decodeMessagingAccount(await api.put(path(accountId), serializeMessagingAccountUpdate(account))),
        delete: async (accountId, expectedRevision): Promise<void> => {
            decodeNoContentResponse(await api.delete(path(accountId), { body: { 'expected_revision': expectedRevision } }), 'Messaging account delete response');
        },
        listMcpTools: async (): Promise<McpFormCatalog> => decodeMessagingMcpCatalog(await api.get('/api/v1/webui/messaging/mcp/tools'))
    };
};

export { createWebuiMessagingAccountEndpoints };
export type { WebuiMessagingAccountEndpoints };
