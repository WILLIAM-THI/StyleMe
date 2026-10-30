// Localhost, or a double-clicked file, use the local backend.
const IS_LOCAL = ['localhost', '127.0.0.1', ''].includes(window.location.hostname);

// The live backend
const LIVE_API = 'https://styleme-api.williamthi.com';

const API_BASE = IS_LOCAL ? 'http://127.0.0.1:8000' : LIVE_API;