const fs = require('fs');
const path = require('path');

const HISTORY_DIR = path.join(__dirname, '../history');

// Ensure history directory exists
if (!fs.existsSync(HISTORY_DIR)) {
    fs.mkdirSync(HISTORY_DIR, { recursive: true });
}

/**
 * Saves the screener results to a JSON file with today's date.
 * @param {Array} results - The filtered list of stocks/FIIs.
 * @param {string} type - 'stock', 'fii', or 'combined'
 * @param {Object} economy - Optional economy data { dollar, selic }
 */
function saveHistory(results, type = 'combined', economy = null) {
    try {
        const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
        const filename = `${today}-${type}-results.json`;
        const filePath = path.join(HISTORY_DIR, filename);

        const data = {
            date: new Date().toISOString(),
            count: results.length,
            economy: economy,
            type: type,
            items: results
        };

        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
        console.log(`💾 History saved to: ${filename}`);
    } catch (error) {
        console.error('❌ Error saving history:', error.message);
    }
}

module.exports = { saveHistory };
