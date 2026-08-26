/* SoAI - Settings page system manager validation [frontend/assets/ts/pages/settings/controllers/systemmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import type { SystemManagerActionId } from '@pages/settings/controllers/systemmanager/contracts.ts';

const { guard: isSystemManagerActionId } = createActionIdSet<SystemManagerActionId>('settings.system.resetAclPolicy', 'settings.system.resetAppearance', 'settings.system.resetMetrics', 'settings.system.resetHardwareHistory', 'settings.system.resetPageLayouts', 'settings.system.resetPreferences', 'settings.system.resetChatPresets', 'settings.system.clearPromptHistory', 'settings.system.resetRecentSearches', 'settings.system.deleteAllConversations', 'settings.system.resetToolApprovalPermissions', 'settings.system.resetPasswordManager', 'settings.system.resetConfiguration', 'settings.system.factoryReset');

export { isSystemManagerActionId };
