/* SoAI - Shared API WebUI [frontend/assets/ts/core/api/endpoints/webui.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { createWebuiAdminEndpoints, type BackupListEntry } from '@core/api/endpoints/webuiAdminEndpoints.ts';
import { createWebuiChatEndpoints } from '@core/api/endpoints/webuiChatEndpoints.ts';
import { createWebuiExternalAccountsEndpoints } from '@core/api/endpoints/webuiExternalAccounts.ts';
import { createWebuiResourceEndpoints } from '@core/api/endpoints/webuiResourceEndpoints.ts';
import { createWebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';
import { createWebuiMessagingAccountEndpoints } from '@core/api/endpoints/webuiMessagingAccounts.ts';
import { createWebuiMediaEndpoints } from '@core/api/endpoints/webuiMedia.ts';
import type { TerminalAccessPolicyResponse } from '@core/api/contracts/terminalAccessContracts.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { decodeWebuiToolIconCatalog, type WebuiToolIconCatalogResponse } from '@core/api/contracts/webuiToolIconContracts.ts';
import { createWebuiLicensingEndpoints } from '@core/api/endpoints/webuiLicensingEndpoints.ts';

const createWebuiEndpoints = (api: ApiClientContext) => {
    return {
        ...createWebuiUserEndpoints(api),
        ...createWebuiAdminEndpoints(api),
        ...createWebuiChatEndpoints(api),
        ...createWebuiResourceEndpoints(api),
        ...createWebuiExternalAccountsEndpoints(api),
        mcp: {
            toolIcons: async (): Promise<WebuiToolIconCatalogResponse> => decodeWebuiToolIconCatalog(await api.get('/api/v1/webui/mcp/tool-icons'))
        },
        messaging: { accounts: createWebuiMessagingAccountEndpoints(api) },
        licensing: createWebuiLicensingEndpoints(api),
        media: createWebuiMediaEndpoints()
    };
};

export { createWebuiEndpoints };
export type { BackupListEntry, TerminalAccessPolicyResponse, WebuiUser };
