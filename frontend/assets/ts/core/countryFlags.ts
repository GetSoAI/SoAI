/* SoAI - ISO country flag asset identities [frontend/assets/ts/core/countryFlags.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssetPath } from '@core/assetPaths.ts';

const countryCodes = new Set(['ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be', 'bf bg bh bi bj bl bm bn bo bq br bs bt bv bw by bz ca cc cd', 'cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm', 'do dz ec ee eg eh er es et fi fj fk fm fo fr ga gb gd ge gf', 'gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu', 'id ie il im in io iq ir is it je jm jo jp ke kg kh ki km kn', 'kp kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me', 'mf mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na', 'nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm', 'pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd se sg sh si', 'sj sk sl sm sn so sr ss st sv sx sy sz tc td tf tg th tj tk', 'tl tm tn to tr tt tv tw tz ua ug um us uy uz va vc ve vg vi', 'vn vu wf ws ye yt za zm zw'].join(' ').split(' '));

const isFlagCountryCode = (value: string): boolean => /^[a-z]{2}$/.test(value) && countryCodes.has(value);

const requireFlagCountryCode = (value: string): string => {
    if (!isFlagCountryCode(value)) throw new TypeError('Invalid ISO flag country code.');
    return value;
};

const flagAssetUrl = (countryCode: string): string => {
    const code = requireFlagCountryCode(countryCode);
    const path = resolveAssetPath(`img/flags/${code}.webp`);
    if (!path) throw new Error('Flag asset path resolution failed.');
    return path;
};

const decodeRegionalIndicatorFlag = (value: string): string | null => {
    const characters = [...value];
    if (characters.length !== 2) return null;
    const indicators = characters.map((character) => character.codePointAt(0));
    const first = indicators[0];
    const second = indicators[1];
    if (first === undefined || second === undefined || first < 0x1f1e6 || first > 0x1f1ff || second < 0x1f1e6 || second > 0x1f1ff) return null;
    const countryCode = String.fromCharCode(first - 0x1f1e6 + 97, second - 0x1f1e6 + 97);
    return isFlagCountryCode(countryCode) ? countryCode : null;
};

export { decodeRegionalIndicatorFlag, flagAssetUrl, isFlagCountryCode, requireFlagCountryCode };
