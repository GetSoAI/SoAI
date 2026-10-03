/* SoAI - SoAI Connect pairing candidates and QR payloads [frontend/assets/ts/pages/settings/controllers/connect/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConnectPairingResponse, ConnectPairingScheme } from '@core/api/contracts/systemConnectPairingContracts.ts';
import type { ConnectBrowserOrigin } from '@pages/settings/contracts/connectManager.ts';

type ConnectCandidateOrigin = 'interface' | 'browser';

interface ConnectCandidate {
    readonly host: string;
    readonly displayHost: string;
    readonly url: string;
    readonly payload: string;
    readonly origin: ConnectCandidateOrigin;
}

const CONNECT_PAIRING_PAYLOAD_MAX_BYTES = 337;
const CONNECT_PAIRING_PAYLOAD_PATTERN = /^[\x21-\x7e]+$/;
const DEFAULT_SCHEME_PORTS: Readonly<Record<ConnectPairingScheme, number>> = Object.freeze({ http: 80, https: 443 });
const LOOPBACK_IPV4_PATTERN = /^127(?:\.\d{1,3}){3}$/;
const LOOPBACK_MAPPED_IPV6_PATTERN = /^::ffff:(?:127(?:\.\d{1,3}){3}|7f[0-9a-f]{2}:[0-9a-f]{1,4})$/;
const UNSPECIFIED_HOSTS: ReadonlySet<string> = new Set(['0.0.0.0', '::']);

const unbracketHost = (host: string): string => (host.startsWith('[') && host.endsWith(']') ? host.slice(1, -1) : host).toLowerCase();

const formatPairingHost = (host: string): string => (host.includes(':') ? `[${host}]` : host);

const isLocalOnlyBrowserHost = (host: string): boolean => UNSPECIFIED_HOSTS.has(host) || host === 'localhost' || host.endsWith('.localhost') || host === '::1' || LOOPBACK_IPV4_PATTERN.test(host) || LOOPBACK_MAPPED_IPV6_PATTERN.test(host);

const buildConnectPairingPayload = (host: string, pairing: ConnectPairingResponse): string | null => {
    const payload = `soai-connect://${formatPairingHost(host)}:${pairing.port}?v=1&scheme=${pairing.scheme}&instance=${pairing.instanceId}`;
    return CONNECT_PAIRING_PAYLOAD_PATTERN.test(payload) && payload.length <= CONNECT_PAIRING_PAYLOAD_MAX_BYTES ? payload : null;
};

const createConnectCandidate = (rawHost: string, origin: ConnectCandidateOrigin, pairing: ConnectPairingResponse): ConnectCandidate | null => {
    const host = unbracketHost(rawHost.trim());
    if (host.length === 0 || host.includes('%')) return null;
    const payload = buildConnectPairingPayload(host, pairing);
    if (payload === null) return null;
    const displayHost = formatPairingHost(host);
    return { host, displayHost, url: `${pairing.scheme}://${displayHost}:${pairing.port}`, payload, origin };
};

const matchesBrowserEndpoint = (pairing: ConnectPairingResponse, browser: ConnectBrowserOrigin): boolean => {
    const port = browser.port === '' ? DEFAULT_SCHEME_PORTS[pairing.scheme] : Number(browser.port);
    return browser.protocol === `${pairing.scheme}:` && port === pairing.port;
};

const resolveConnectCandidates = (pairing: ConnectPairingResponse, browser: ConnectBrowserOrigin): readonly ConnectCandidate[] => {
    const candidates: ConnectCandidate[] = [];
    const append = (candidate: ConnectCandidate | null): void => {
        if (candidate !== null && !candidates.some((existing) => existing.host === candidate.host)) candidates.push(candidate);
    };
    pairing.addresses.forEach((address) => append(createConnectCandidate(address, 'interface', pairing)));
    const browserHost = unbracketHost(browser.hostname);
    if (matchesBrowserEndpoint(pairing, browser) && !isLocalOnlyBrowserHost(browserHost)) append(createConnectCandidate(browserHost, 'browser', pairing));
    return candidates;
};

export { resolveConnectCandidates };
export type { ConnectCandidate };
