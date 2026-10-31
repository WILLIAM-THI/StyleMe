/* menu.js - login check + menu overlay, for pages that don't have the saved
   outfits carousel (wardrobe, add item, edit item). dashboard.html and
   settings.html use the fuller js/common.js instead. */


if (!localStorage.getItem('user_token')) window.location.replace('index.html');

fetch(`${API_BASE}/api/me`, { headers: { Authorization: 'Bearer ' + localStorage.getItem('user_token') } })
    .then(res => { if (res.status === 401) { localStorage.removeItem('user_token'); window.location.replace('index.html'); } })
    .catch(() => { /* backend offline: stay on the page */ });

function authHeader() { return { Authorization: 'Bearer ' + localStorage.getItem('user_token') }; }

const menuBtn = document.getElementById('menuBtn');
const menu = document.getElementById('menu');
const backdrop = document.getElementById('backdrop');

function setMenu(open) {
    menu.classList.toggle('open', open);
    backdrop.classList.toggle('open', open);
    menuBtn.setAttribute('aria-expanded', String(open));
    if (open) menu.querySelector('a').focus(); else menuBtn.focus();
}
menuBtn.addEventListener('click', () => setMenu(true));
document.getElementById('menuClose').addEventListener('click', () => setMenu(false));
backdrop.addEventListener('click', () => setMenu(false));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('open')) setMenu(false); });
