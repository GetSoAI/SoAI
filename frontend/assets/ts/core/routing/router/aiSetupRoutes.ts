/* SoAI - Shared routing AI setup resume and chat handoff routes [frontend/assets/ts/core/routing/router/aiSetupRoutes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRouteRegistry } from '@core/routeregistry/service.ts';
import { AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';
import { buildQueryRoute } from '@core/routing/router/events.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const AI_SETUP_RESUME_PARAMETER = 'resume';
const AI_SETUP_RESUME_VALUE = 'ai-setup';
const AI_SETUP_HANDOFF_PARAMETER = 'ai_setup_handoff';
const AI_SETUP_HANDOFF_VALUE = '1';
const CHAT_ROUTE_ID = 'chat';

const requireChatRoutePath = (): string => {
    const route = getRouteRegistry()[CHAT_ROUTE_ID];
    if (route === undefined) throw new Error('Chat route is not registered');
    return route.path;
};

const buildAiSetupResumeRoute = (): string => buildQueryRoute(AUTH_ROUTE_WIZARD, { [AI_SETUP_RESUME_PARAMETER]: AI_SETUP_RESUME_VALUE });

const buildAiSetupHandoffRoute = (): string => buildQueryRoute(requireChatRoutePath(), { [AI_SETUP_HANDOFF_PARAMETER]: AI_SETUP_HANDOFF_VALUE });

const isAiSetupResumeRequest = (parameters: Readonly<Record<string, JsonValue | undefined>> | null): boolean => parameters?.[AI_SETUP_RESUME_PARAMETER] === AI_SETUP_RESUME_VALUE;

const isAiSetupHandoffRequest = (parameters: Readonly<Record<string, JsonValue | undefined>> | null): boolean => parameters?.[AI_SETUP_HANDOFF_PARAMETER] === AI_SETUP_HANDOFF_VALUE;

export { buildAiSetupHandoffRoute, buildAiSetupResumeRoute, isAiSetupHandoffRequest, isAiSetupResumeRequest };
