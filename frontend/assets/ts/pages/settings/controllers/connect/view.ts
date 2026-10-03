/* SoAI - SoAI Connect settings markup [frontend/assets/ts/pages/settings/controllers/connect/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConnectPairingResponse } from '@core/api/contracts/systemConnectPairingContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { SettingsCapabilityAvailability } from '@core/settings/contracts.ts';
import { renderSection } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarRefreshButton } from '@core/settings/titlebarActions.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { renderSettingsCapabilityNotice } from '@features/settings/public.ts';
import type { ConnectCandidate } from '@pages/settings/controllers/connect/mappers.ts';

interface ConnectViewState {
    readonly pairing: ConnectPairingResponse | null;
    readonly availability: SettingsCapabilityAvailability;
    readonly candidates: readonly ConnectCandidate[];
    readonly selectedIndex: number;
}

const escaped = (value: string): string => securityApi.escapeHtml(value);
const icon = (name: IconName, size = 16): TrustedHtml => renderIconSlot(getIconSync(name, { size, strokeWidth: 1.6 }));

const renderCallout = (tone: 'warning' | 'info', iconName: IconName, title: string, body: string): string => `<div class="settings-connect__callout settings-connect__callout--${tone}" role="note">${icon(iconName, 18)}<div class="settings-connect__callout-body"><strong>${escaped(title)}</strong>${body}</div></div>`;

const renderLoopbackWarning = (): string => renderCallout('warning', 'warning', i18n.t('settings.connect.loopbackWarningTitle'), `<p>${escaped(i18n.t('settings.connect.loopbackWarningMessage'))}</p><p><code>SERVER.HTTP.NETWORK.HOST = 0.0.0.0</code></p>`);

const renderStagePlaceholder = (message: string, empty: boolean): string => {
    const emptyContent = empty ? `${icon('device-network', 28)}<strong>${escaped(i18n.t('settings.connect.noAddressesTitle'))}</strong>` : '';
    return `<div class="settings-connect__stage settings-connect__stage--${empty ? 'empty' : 'loading'}"${empty ? '' : ' aria-busy="true"'}>${emptyContent}<p class="setting-help">${escaped(message)}</p></div>`;
};

const renderEndpoint = (candidate: ConnectCandidate, pairing: ConnectPairingResponse): string => {
    const copyLabel = i18n.t('settings.connect.copyAddress');
    const endpoint = `<span class="settings-connect__endpoint-scheme">${pairing.scheme}://</span><span class="settings-connect__endpoint-host">${escaped(candidate.displayHost)}</span><span class="settings-connect__endpoint-scheme">:</span><span class="settings-connect__endpoint-port">${pairing.port}</span>`;
    return `<div class="settings-connect__endpoint"><span class="settings-connect__endpoint-text">${endpoint}</span><button type="button" class="ui-icon-button ui-icon-button--xs ui-variant-ghost settings-connect__copy-button" data-action="connect-copy-address" ${renderLabelAttributes(copyLabel)}>${icon('copy', 14)}</button></div>`;
};

const renderAddressChooser = (state: ConnectViewState): string => {
    if (state.candidates.length < 2) return '';
    const label = i18n.t('settings.connect.chooseAddress');
    const chips = state.candidates
        .map((candidate, index) => {
            const selected = index === state.selectedIndex;
            const browserHint = candidate.origin === 'browser' ? i18n.t('settings.connect.browserAddress') : null;
            const labels = browserHint === null ? { ariaLabel: candidate.displayHost, tooltip: candidate.displayHost } : { ariaLabel: `${candidate.displayHost} · ${browserHint}`, tooltip: browserHint };
            return `<button type="button" class="settings-connect__chip${selected ? ' is-selected' : ''}" role="radio" aria-checked="${selected}" tabindex="${selected ? 0 : -1}" data-action="connect-select-address" data-address-index="${index}" ${renderLabelAttributes(labels)}>${selected ? icon('check', 14) : ''}<span>${escaped(candidate.displayHost)}</span></button>`;
        })
        .join('');
    return `<div class="settings-connect__chooser"><span class="settings-connect__chooser-label" id="settings-connect-chooser-label">${escaped(label)}</span><div class="settings-connect__chips" role="radiogroup" aria-labelledby="settings-connect-chooser-label">${chips}</div></div>`;
};

const renderPairingBody = (state: ConnectViewState): string => {
    const pairing = state.pairing;
    if (pairing === null) return state.availability.status === 'pending' ? renderStagePlaceholder(i18n.t('common.loading'), false) : '';
    const candidate = state.candidates[state.selectedIndex];
    if (candidate === undefined) return renderStagePlaceholder(i18n.t('settings.connect.noAddressesMessage'), true);
    const qrLabel = i18n.t('settings.connect.qrLabel', { address: candidate.url });
    const stage = `<div class="settings-connect__stage"><canvas class="settings-connect__qr" role="img" aria-label="${securityApi.escapeAttribute(qrLabel)}"></canvas></div>`;
    return `${stage}<p class="setting-help">${escaped(i18n.t('settings.connect.scanHint'))}</p>${renderEndpoint(candidate, pairing)}${renderAddressChooser(state)}`;
};

const renderPairingCard = (state: ConnectViewState): string => {
    const warning = state.pairing?.bindScope === 'loopback' ? renderLoopbackWarning() : '';
    return `<div class="settings-connect__pairing">${renderSettingsCapabilityNotice(state.availability)}${warning}${renderPairingBody(state)}</div>`;
};

const renderGuideCard = (): string => {
    const steps = [i18n.t('settings.connect.stepInstall'), i18n.t('settings.connect.stepScan'), i18n.t('settings.connect.stepSignIn')].map((step, index) => `<li><span class="ui-model-type-badge ${getBadgeColorClass(`connect-step-${index + 1}`)} settings-connect__step-number" aria-hidden="true">${index + 1}</span><span>${escaped(step)}</span></li>`).join('');
    const documentationLabel = i18n.t('settings.connect.documentationLink');
    const documentation = `<p class="setting-help">${escaped(i18n.t('settings.connect.documentationHint'))}</p><button type="button" class="ui-button ui-button--sm ui-variant-neutral external-link-confirmation" data-href="${securityApi.escapeAttribute(`${SOAI_WEBSITE_URL}/documentation`)}" data-external-link-type="about-documentation" ${renderLabelAttributes(documentationLabel)}>${icon('external-link', 14)}<span>${escaped(documentationLabel)}</span></button>`;
    const vpn = renderCallout('info', 'info', i18n.t('settings.connect.vpnTitle'), `<p>${escaped(i18n.t('settings.connect.vpnHint'))}</p>`);
    return `<div class="settings-record-item settings-connect__guide"><h3 class="subgroup-title">${escaped(i18n.t('settings.connect.stepsTitle'))}</h3><ol class="settings-connect__steps">${steps}</ol>${vpn}<div class="settings-connect__documentation">${documentation}</div></div>`;
};

const renderConnectSettings = (state: ConnectViewState): TrustedHtml =>
    toTrustedUiHtml(
        renderSection({
            title: i18n.t('settings.connect.title'),
            description: i18n.t('settings.connect.description'),
            className: 'settings-section--connect',
            trailing: renderSettingsTitlebarRefreshButton({ action: 'connect-refresh', label: i18n.t('settings.connect.refresh') }),
            content: `<div class="settings-connect">${renderPairingCard(state)}${renderGuideCard()}</div>`
        })
    );

export { renderConnectSettings };
export type { ConnectViewState };
