/* SoAI - Planned HTTP/HTTPS address handoff resolution [frontend/assets/ts/core/connectionHandoff.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConnectionScheme, ConnectionTransition } from '@core/restartStateGateway.ts';
import { resolveHttpUrl } from '@core/security/public.ts';

type ConnectionHandoff = { type: 'address'; url: string } | { type: 'manual'; requestedScheme: ConnectionScheme };

const DEFAULT_PORTS: Readonly<Record<ConnectionScheme, string>> = { http: '80', https: '443' };

const resolveOrigin = (value: string, baseUrl: string): string | null => {
    const resolved = resolveHttpUrl(value, baseUrl);
    return resolved === null ? null : new URL(resolved).origin;
};

const withPageRoute = (origin: string, page: URL): string | null => resolveHttpUrl(`${origin}${page.pathname}${page.search}${page.hash}`);

const isDirectListenerPage = (transition: ConnectionTransition, page: URL, apiBaseUrl: string | null): boolean => page.protocol === `${transition.currentScheme}:` && (apiBaseUrl === null || !apiBaseUrl.trim() || resolveOrigin(apiBaseUrl, page.href) === page.origin);

const resolveSameAddress = (transition: ConnectionTransition, page: URL): string | null => {
    const target = new URL(page.href);
    const port = page.port || DEFAULT_PORTS[transition.currentScheme];
    target.username = '';
    target.password = '';
    target.protocol = `${transition.requestedScheme}:`;
    target.port = port;
    return resolveHttpUrl(target.href);
};

const resolveConnectionHandoff = (transition: ConnectionTransition | null, pageHref: string, apiBaseUrl: string | null): ConnectionHandoff | null => {
    if (transition === null || transition.requestedScheme === transition.currentScheme) return null;
    const page = new URL(pageHref);
    const manual: ConnectionHandoff = { type: 'manual', requestedScheme: transition.requestedScheme };
    if (transition.destination === 'manual') return manual;
    if (transition.destination === 'public_origin') {
        const origin = transition.publicOrigin === null ? null : resolveOrigin(transition.publicOrigin, page.href);
        if (origin === page.origin) return null;
        const url = origin === null ? null : withPageRoute(origin, page);
        return url === null ? manual : { type: 'address', url };
    }
    if (!isDirectListenerPage(transition, page, apiBaseUrl)) return manual;
    const url = resolveSameAddress(transition, page);
    return url === null ? manual : { type: 'address', url };
};

export { resolveConnectionHandoff };
export type { ConnectionHandoff };
