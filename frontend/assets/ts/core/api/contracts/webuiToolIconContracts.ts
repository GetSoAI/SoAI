/* SoAI - Frontend WebUI tool icon response contracts [frontend/assets/ts/core/api/contracts/webuiToolIconContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { requireSupportedSvgDataUri } from '@core/svgSanitizer.ts';

interface WebuiToolIcon {
    toolName: string;
    src: string;
}

interface WebuiToolIconCatalogResponse {
    icons: WebuiToolIcon[];
}

const decodeWebuiToolIconCatalog = (value: ApiResponsePayload): WebuiToolIconCatalogResponse => {
    const response = requireRecord(value, 'WebUI tool icon catalog response');
    const iconRecords = readRequiredJsonObjectArrayValue(response['icons'], 'WebUI tool icon catalog response.icons');
    return {
        icons: iconRecords.map((icon, index) => ({
            toolName: readRequiredTrimmedStringValue(icon['tool_name'], `WebUI tool icon catalog response.icons[${String(index)}].tool_name`),
            src: requireSupportedSvgDataUri(readRequiredTrimmedStringValue(icon['src'], `WebUI tool icon catalog response.icons[${String(index)}].src`))
        }))
    };
};

export { decodeWebuiToolIconCatalog };
export type { WebuiToolIcon, WebuiToolIconCatalogResponse };
