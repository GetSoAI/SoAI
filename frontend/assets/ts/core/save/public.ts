/* SoAI - Save controller public surface [frontend/assets/ts/core/save/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { SAVE_HEADER_PRIORITY_MODAL, SAVE_HEADER_PRIORITY_PAGE } from '@core/save/constants.ts';
export { createSaveController } from '@core/save/controller.ts';
export { resetSaveHeaderActionState } from '@core/save/binding.ts';
export type { SaveAdmission, SaveController } from '@core/save/controller.ts';
export type { PreparedSaveUnit, SaveRequestOutcome, SaveUnit, SaveUnitResult } from '@core/save/contracts.ts';

export { createExclusiveSaveAdmission } from '@core/save/admission.ts';
