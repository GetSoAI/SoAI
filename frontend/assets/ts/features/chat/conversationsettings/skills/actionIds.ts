/* SoAI - Skill conversation settings action identifiers [frontend/assets/ts/features/chat/conversationsettings/skills/actionIds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

type SkillAction = 'skills-add' | 'skills-upload' | 'skills-toggle' | 'skills-search' | 'skills-details' | 'skills-remove' | 'skills-use-latest' | 'skills-retry-import' | 'skills-keep' | 'skills-download' | 'skills-close-details';

const { guard: isSkillAction } = createActionIdSet<SkillAction>('skills-add', 'skills-upload', 'skills-toggle', 'skills-search', 'skills-details', 'skills-remove', 'skills-use-latest', 'skills-retry-import', 'skills-keep', 'skills-download', 'skills-close-details');

export { isSkillAction };
export type { SkillAction };
