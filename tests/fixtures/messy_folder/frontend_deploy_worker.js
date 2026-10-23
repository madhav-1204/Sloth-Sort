const { execSync } = require('child_process');
console.log('Building production static frontend bundle...');
execSync('npm run build', { stdio: 'inherit' });
console.log('Deploying to CDN edge storage bucket...');
