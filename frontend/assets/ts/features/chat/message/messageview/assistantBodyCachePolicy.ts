/* SoAI - Chat feature assistant body cache policy [frontend/assets/ts/features/chat/message/messageview/assistantBodyCachePolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { shouldCollapseLoadingActivities } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';

export const resolveShouldCacheSettledAssistantBody = (inputArguments: { message: ChatMessage; isShowActivitiesEnabled: boolean; collapsedState: boolean | null }): boolean => {
    if (shouldCollapseLoadingActivities({ isShowActivitiesEnabled: inputArguments.isShowActivitiesEnabled, collapsedOverride: inputArguments.collapsedState })) {
        return false;
    }
    const loadingActivity = resolveLatestLoadingActivityFromMessage(inputArguments.message);
    if (loadingActivity !== null) {
        return false;
    }
    const content = inputArguments.message.content;
    if (isString(content) && content.length >= 4000) {
        return true;
    }
    if (isArray(content) && content.length >= 25) {
        return true;
    }
    const toolCallCount = isArray(inputArguments.message.toolCalls) ? inputArguments.message.toolCalls.length : 0;
    if (toolCallCount >= 12) {
        return true;
    }
    const timelineCount = isArray(inputArguments.message.assistantEventTimeline) ? inputArguments.message.assistantEventTimeline.length : 0;
    if (timelineCount >= 30) {
        return true;
    }
    return false;
};
