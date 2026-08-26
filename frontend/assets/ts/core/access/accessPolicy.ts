/* SoAI - Central UI access policy helpers for route, sidebar, search, and settings gates [frontend/assets/ts/core/access/accessPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouteDefinition } from '@core/routeregistry/contracts.ts';

interface UiAccessContext {
    isAuthenticated: boolean;
    isAdmin: boolean;
    soaiOsAvailable: boolean;
    terminalAllowed: boolean | null;
    grantedActions: ReadonlySet<string>;
}

interface UiAccessRequirement {
    authenticated: boolean;
    admin: boolean;
    soaiOs: boolean;
    terminal: boolean;
    actions: readonly string[];
}

interface AuthAccessSource {
    readonly isAuthenticated: boolean;
    isAdmin: () => boolean;
}

interface CurrentUserAccessSource {
    readonly isAdmin?: boolean | undefined;
}

interface UiAccessContextInput {
    isAuthenticated: boolean;
    isAdmin: boolean;
    soaiOsAvailable?: boolean | undefined;
    terminalAllowed?: boolean | null | undefined;
    grantedActions?: ReadonlySet<string> | undefined;
}

interface UiAccessContextOverrides {
    soaiOsAvailable?: boolean | undefined;
    terminalAllowed?: boolean | null | undefined;
    grantedActions?: ReadonlySet<string> | undefined;
}

interface UiAccessRequirementInput {
    authenticated?: boolean | undefined;
    admin?: boolean | undefined;
    soaiOs?: boolean | undefined;
    terminal?: boolean | undefined;
    actions?: readonly string[] | undefined;
}

const EMPTY_ACTIONS: ReadonlySet<string> = new Set();

const createAccessContext = (input: UiAccessContextInput): UiAccessContext => ({
    isAuthenticated: input.isAuthenticated,
    isAdmin: input.isAdmin,
    soaiOsAvailable: input.soaiOsAvailable ?? false,
    terminalAllowed: input.terminalAllowed ?? null,
    grantedActions: input.grantedActions ?? EMPTY_ACTIONS
});

const createAccessContextFromAuth = (auth: AuthAccessSource, input: UiAccessContextOverrides = {}): UiAccessContext =>
    createAccessContext({
        isAuthenticated: auth.isAuthenticated === true,
        isAdmin: auth.isAdmin(),
        soaiOsAvailable: input.soaiOsAvailable,
        terminalAllowed: input.terminalAllowed,
        grantedActions: input.grantedActions
    });

const createAccessContextFromUser = (user: CurrentUserAccessSource | null, input: UiAccessContextOverrides = {}): UiAccessContext =>
    createAccessContext({
        isAuthenticated: user !== null,
        isAdmin: user?.isAdmin === true,
        soaiOsAvailable: input.soaiOsAvailable,
        terminalAllowed: input.terminalAllowed,
        grantedActions: input.grantedActions
    });

const createAccessRequirement = (input: UiAccessRequirementInput): UiAccessRequirement => ({
    authenticated: input.authenticated === true,
    admin: input.admin === true,
    soaiOs: input.soaiOs === true,
    terminal: input.terminal === true,
    actions: input.actions ?? []
});

const createRouteAccessRequirement = (route: Pick<RouteDefinition, 'auth' | 'adminOnly' | 'component'> & { actions?: readonly string[] | undefined }): UiAccessRequirement =>
    createAccessRequirement({
        authenticated: route.auth === true,
        admin: route.adminOnly === true,
        terminal: route.component === 'terminal',
        actions: route.actions
    });

const createSettingsTabAccessRequirement = (definition: { adminOnly?: boolean; osOnly?: boolean; actions?: readonly string[] }): UiAccessRequirement =>
    createAccessRequirement({
        authenticated: true,
        admin: definition.adminOnly === true,
        soaiOs: definition.osOnly === true,
        actions: definition.actions
    });

const canAccessUiSurface = (requirement: UiAccessRequirement, context: UiAccessContext): boolean => {
    if (requirement.authenticated && !context.isAuthenticated) {
        return false;
    }
    if (requirement.admin && !context.isAdmin) {
        return false;
    }
    if (requirement.soaiOs && !context.soaiOsAvailable) {
        return false;
    }
    if (requirement.terminal && context.terminalAllowed !== true) {
        return false;
    }
    for (const action of requirement.actions) {
        if (!context.grantedActions.has(action)) {
            return false;
        }
    }
    return true;
};

export { canAccessUiSurface, createAccessContext, createAccessContextFromAuth, createAccessContextFromUser, createAccessRequirement, createRouteAccessRequirement, createSettingsTabAccessRequirement };
export type { AuthAccessSource, CurrentUserAccessSource, UiAccessContext, UiAccessContextInput, UiAccessContextOverrides, UiAccessRequirement, UiAccessRequirementInput };
