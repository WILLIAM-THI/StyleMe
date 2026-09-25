const API_BASE = 'http://127.0.0.1:8000';   // same address as on the login/sign up pages

// ----- Check the login token is still valid -----
fetch(`${API_BASE}/api/me`, { headers: { Authorization: 'Bearer ' + localStorage.getItem('user_token') } })
    .then(res => {
        if (res.status === 401) {
            localStorage.removeItem('user_token');
            window.location.replace('index.html');
        }
    })
    .catch(() => { /* backend offline: stay on the page */ });

// ----- Fullscreen viewer -----
const viewer = document.getElementById('viewer');
const viewerImg = document.getElementById('viewerImg');
const viewerPh = document.getElementById('viewerPh');

function openFront() {
    const outfit = savedOutfits[current];
    if (outfit.empty) { window.location.href = 'generate-outfit.html'; return; }
    viewerImg.hidden = !outfit.image;
    viewerPh.hidden = !!outfit.image;
    if (outfit.image) { viewerImg.src = outfit.image; viewerImg.alt = 'Saved outfit'; }
    viewer.hidden = false;
    document.body.style.overflow = 'hidden';
    document.getElementById('viewerClose').focus();
}
function closeViewer() {
    viewer.hidden = true;
    viewerImg.removeAttribute('src');
    document.body.style.overflow = '';
}
viewer.addEventListener('click', closeViewer);

// ----- Menu overlay -----
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
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!viewer.hidden) closeViewer();
    else if (menu.classList.contains('open')) setMenu(false);
});

// ----- Saved outfits: stacked cards -----
let savedOutfits = [
    { id: 1, image: '' },
    { id: 2, image: '' },
    { id: 3, image: '' }
];
if (savedOutfits.length === 0) savedOutfits = [{ empty: true, image: '' }];

const stack = document.getElementById('stack');
const dotsBox = document.getElementById('dots');
const cards = [];
let current = 0;

savedOutfits.forEach((outfit, i) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'card';
    card.dataset.index = i;
    card.setAttribute('aria-label', outfit.empty ? 'No saved outfits yet. Create one' : 'Open outfit ' + (i + 1));
    if (outfit.image) {
        const img = document.createElement('img');
        img.src = outfit.image;
        img.alt = '';
        img.draggable = false;
        card.appendChild(img);
    } else {
        const ph = document.createElement('span');
        ph.className = 'card-placeholder';
        ph.textContent = '👗';
        card.appendChild(ph);
    }
    stack.appendChild(card);
    cards.push(card);
});

// Puts every card in the right place: front, behind, far behind, or swiped away
function render() {
    cards.forEach((card, i) => {
        const offset = i - current;
        card.dataset.pos = offset < 0 ? 'gone' : offset === 0 ? 'front' : offset <= 2 ? 'behind' : 'far';
        card.style.setProperty('--o', Math.min(Math.max(offset, 0), 3));
        card.style.zIndex = 10 - Math.abs(offset);
        card.tabIndex = offset === 0 ? 0 : -1;
    });
    [...dotsBox.children].forEach((d, i) => d.classList.toggle('active', i === current));
}
function go(i) {
    current = Math.max(0, Math.min(cards.length - 1, i));
    render();
}

if (cards.length > 1) {
    cards.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.className = 'dot';
        dot.setAttribute('aria-label', 'Show outfit ' + (i + 1));
        dot.addEventListener('click', () => go(i));
        dotsBox.appendChild(dot);
    });
}
render();

// Swipe to change card, tap the front card to open it, tap a card behind to bring it forward
let startX = null;
stack.addEventListener('pointerdown', (e) => { startX = e.clientX; });
stack.addEventListener('pointercancel', () => { startX = null; });
stack.addEventListener('pointerup', (e) => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    startX = null;
    if (dx < -40) return go(current + 1);
    if (dx > 40) return go(current - 1);
    const card = e.target.closest('.card');
    if (!card) return;
    const index = Number(card.dataset.index);
    if (index === current) openFront(); else go(index);
});
stack.addEventListener('click', (e) => { if (e.detail === 0 && e.target.closest('.card')?.dataset.pos === 'front') openFront(); });
stack.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') go(current + 1);
    if (e.key === 'ArrowLeft') go(current - 1);
});
