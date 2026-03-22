const axios = require('axios');
const iconv = require('iconv-lite');
const fs = require('fs');

async function dumpMobileFundamentus() {
    const url = 'https://www.fundamentus.com.br/detalhes.php?papel=BOVA11&interface=mobile';
    try {
        const response = await axios.get(url, {
            responseType: 'arraybuffer',
            headers: {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            }
        });
        const decoded = iconv.decode(response.data, 'latin1');
        fs.writeFileSync('fundamentus_mobile_dump.html', decoded);
        console.log('Dump saved to fundamentus_mobile_dump.html');
    } catch (err) {
        console.error(err);
    }
}

dumpMobileFundamentus();
