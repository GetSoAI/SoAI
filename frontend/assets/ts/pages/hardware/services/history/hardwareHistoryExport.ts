/* SoAI - Hardware page history export [frontend/assets/ts/pages/hardware/services/history/hardwareHistoryExport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { serializeHardwareExportRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { ExportPreviewModalOpenRequest } from '@features/exportpreview/public.ts';
import type { HistoryRequestParameters } from '@pages/hardware/types.ts';

type HardwareExportSnapshotPayload = JsonObject;

const buildHardwareExportSnapshotRequest = (queryParameters: HistoryRequestParameters): ExportPreviewModalOpenRequest => {
    const componentRaw = queryParameters['component'];
    const component = isString(componentRaw) && componentRaw.trim() ? componentRaw.trim() : null;
    const identifierRaw = queryParameters['identifier'];
    const identifier = isString(identifierRaw) && identifierRaw.trim() ? identifierRaw.trim() : null;
    const gpuIndexRaw = queryParameters.gpuIndex;
    const gpuIndex = isFiniteNumber(gpuIndexRaw) && Number.isInteger(gpuIndexRaw) && gpuIndexRaw >= 0 ? gpuIndexRaw : null;
    if (!component) {
        throw new Error('Cannot export hardware history: missing component');
    }
    const payload: HardwareExportSnapshotPayload = serializeHardwareExportRequest({
        component,
        identifier: identifier ?? undefined,
        gpuIndex: gpuIndex ?? undefined
    });
    return {
        snapshotResource: 'hardware.export',
        payload,
        scope: 'hardware',
        boundaryName: 'hardware:openExportPreviewModal',
        downloadBoundaryName: 'hardware:downloadExportPreview'
    };
};

export { buildHardwareExportSnapshotRequest };
export type { HardwareExportSnapshotPayload };
