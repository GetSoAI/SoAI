/* SoAI - Chat page base host [frontend/assets/ts/pages/chat/controllers/chatpage/construction/baseHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { AiSetupStateUpdate } from '@core/storage/service/aiSetupActions.ts';
import type { ChatPreferencesManager, SessionData } from '@core/storage/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatTextZoomPageHost } from '@pages/chat/state/ChatSettingsStateManager.ts';

interface ChatPageStorageSource {
    ready: Promise<void>;
    getAiSetup: () => AiSetupState | null;
    updateAiSetup: (update: AiSetupStateUpdate) => AiSetupState | null;
    isAiSetupResumable: () => boolean;
    session?: SessionData;
    getChatTextZoom: (defaultZoom: number) => number;
    setChatTextZoom: (value: number) => void;
    getChatPreferences: () => ChatPreferencesManager;
    setChatPreferences: (preferences: JsonValue) => void;
    getChatWidescreenMode: () => boolean;
    setChatWidescreenMode: (value: boolean) => void;
    getChatSidebarOpen: () => boolean;
    setChatSidebarOpen: (value: boolean) => void;
    getChatShowFavoritesAtTop: () => boolean;
    setChatShowFavoritesAtTop: (value: boolean) => void;
    getChatPlanBarVisible: () => boolean;
    setChatPlanBarVisible: (value: boolean) => void;
    getCodeRecognitionEnabled: () => boolean;
    getAssistantAvatar: () => string | null;
    setAssistantAvatar: (value: string | null) => void;
    getUserAvatar: () => string | null;
    setUserAvatar: (value: string | null) => void;
}

export type { ChatPageStorageSource, ChatTextZoomPageHost };
