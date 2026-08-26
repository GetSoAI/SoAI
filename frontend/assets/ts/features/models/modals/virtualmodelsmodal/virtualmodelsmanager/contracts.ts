/* SoAI - Virtual model collection and control contracts [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodelsmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';

interface ModelsCollectionView {
    getAll(): ResourceItem[];
}

type VirtualModelsValueControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

type VirtualModelSelectionPayload = { universalId: string };

export type { ModelsCollectionView, VirtualModelSelectionPayload, VirtualModelsValueControl };
export type { ModelRecord };
