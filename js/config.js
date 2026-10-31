// config.js - the place that says where the backend lives.

// On your own computer (Live Server, localhost, or a double-clicked file) use the local backend.
const IS_LOCAL = ['localhost', '127.0.0.1', ''].includes(window.location.hostname);

// Live backend.
const LIVE_API = 'https://styleme-api.williamthi.com';

const API_BASE = IS_LOCAL ? 'http://127.0.0.1:8000' : LIVE_API;

// While testing on your own computer the backend gives photo addresses like "/uploads/abc.jpg".
// (On the live site, S3 gives full https:// addresses and are used as they are.)
function photoUrl(url) {
    return url && url.startsWith('/') ? API_BASE + url : url;
}
