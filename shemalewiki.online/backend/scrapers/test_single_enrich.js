const enrichProfile = require('./enrich');

async function test() {
  console.log('Testing enrichment scraper on active database models...');
  try {
    console.log('\n--- Model 1: Erika Backster ---');
    await enrichProfile('1691', 'Erika Backster', '');
    console.log('\n--- Model 2: Jessica The Fox ---');
    await enrichProfile('2110', 'Jessica The Fox', '');
    console.log('\n--- Model 3: Taissi Fontini ---');
    await enrichProfile('2003', 'Taissi Fontini', '');
  } catch (err) {
    console.error('Test single enrichment error:', err);
  }
}

test();
