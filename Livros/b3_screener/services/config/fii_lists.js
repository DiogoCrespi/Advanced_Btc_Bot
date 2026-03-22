// services/config/fii_lists.js

/**
 * Hardcoded lists of FII tickers for classification and fallback purposes.
 * These lists are used to improve classification accuracy when metadata is ambiguous or missing.
 */

// Well-known non-infra tickers that should never be tagged as INFRA
const NEVER_INFRA = [
    'MXRF11', 'HGLG11', 'KNRI11', 'XPLG11', 'VISC11', 'VINO11',
    'BCFF11', 'XPML11', 'BTLG11', 'TRXF11', 'KNCR11', 'RECR11'
];

// Known FI-AGRO tickers
const KNOWN_FIAGROS = [
    'SNAG11', 'KNCA11', 'VGIA11', 'RURA11', 'FGAA11', 'RZAG11',
    'OIAG11', 'AGRX11', 'NCRA11', 'XPCA11', 'BTRA11', 'VCRA11',
    'BBGO11'
];

// Known FI-INFRA tickers (Union of lists from fiis.js and fi_infra.js fallback)
const KNOWN_INFRAS = [
    'BDIF11', 'JURO11', 'KDIF11', 'CPTI11', 'VIGT11', 'BIDB11',
    'CDII11', 'IFRA11', 'IFRI11', 'BINC11', 'BODB11', 'JMBI11',
    'XPID11', 'ISNT11', 'ISEN11', 'ISTT11', 'DIVS11', 'VINF11',
    'NUIF11', 'RBIF11', 'SNID11', 'VANG11'
];

module.exports = {
    NEVER_INFRA,
    KNOWN_FIAGROS,
    KNOWN_INFRAS
};
