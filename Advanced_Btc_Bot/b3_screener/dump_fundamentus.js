const axios = require('axios');
const iconv = require('iconv-lite');
const fs = require('fs');

async function dumpFundamentus() {
    const url = 'https://www.fundamentus.com.br/detalhes.php?papel=BOVA11';
    try {
        const response = await axios.get(url, {
            responseType: 'arraybuffer',
            headers: { 'User-Agent': 'Mozilla/5.0' }
        });
        const decoded = iconv.decode(response.data, 'latin1');
        fs.writeFileSync('fundamentus_dump.html', decoded);
        console.log('Dump saved to fundamentus_dump.html');
    } catch (err) {
        console.error(err);
    }
}

dumpFundamentus();
