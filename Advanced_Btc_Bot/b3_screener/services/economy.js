const axios = require('axios');

async function getDollarRate() {
    try {
        const response = await axios.get('https://economia.awesomeapi.com.br/last/USD-BRL');
        return parseFloat(response.data.USDBRL.bid);
    } catch (error) {
        console.error('Error fetching Dollar rate:', error.message);
        return null;
    }
}

async function getSelicRate() {
    try {
        // BCB API returns an array, e.g. [{"data":"06/02/2026","valor":"10.75"}]
        // This is the metadata endpoint for the daily rate of the Selic Over.
        // For the *Target* Selic (Meta Selic), code is 432.
        // Let's use code 432 for the target rate which is more common for "Selic Atual".
        const response = await axios.get('https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json');
        return parseFloat(response.data[0].valor);
    } catch (error) {
        console.error('Error fetching Selic rate:', error.message);
        return null;
    }
}

module.exports = { getDollarRate, getSelicRate };
