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
const viewerStage = document.getElementById('viewerStage');

function openFront() {
    const outfit = savedOutfits[current];
    if (outfit.empty) { window.location.href = 'weather-outfit.html'; return; }
    renderOutfit(viewerStage, outfit.items);
    viewer.hidden = false;
    document.body.style.overflow = 'hidden';
    document.getElementById('viewerClose').focus();
}
function closeViewer() {
    viewer.hidden = true;
    viewerStage.innerHTML = '';
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
const MAX_CARDS = 8;   // the newest outfits; the Saved Outfits page shows them all

let savedOutfits = [];   // [{ id, items: [...] }], or a single { empty: true } when there are none yet
const stack = document.getElementById('stack');
const dotsBox = document.getElementById('dots');
let cards = [];
let current = 0;

function buildCards() {
    stack.innerHTML = '';
    dotsBox.innerHTML = '';
    cards = [];
    current = 0;
    if (savedOutfits.length === 0) savedOutfits = [{ empty: true }];

    savedOutfits.forEach((outfit, i) => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'card';
        card.dataset.index = i;
        card.setAttribute('aria-label', outfit.empty ? 'No saved outfits yet. Create one' : 'Open outfit ' + (i + 1));
        if (outfit.empty) {
            const ph = document.createElement('span');
            ph.className = 'card-placeholder';
            ph.textContent = '👗';
            card.appendChild(ph);
        } else {
            const outfitStage = document.createElement('div');
            outfitStage.className = 'outfit-stage';
            renderOutfit(outfitStage, outfit.items);
            card.appendChild(outfitStage);
        }
        stack.appendChild(card);
        cards.push(card);
    });

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
}

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

async function loadSavedOutfits() {
    try {
        const res = await fetch(`${API_BASE}/api/outfits`, { headers: { Authorization: 'Bearer ' + localStorage.getItem('user_token') } });
        if (res.status === 401) return; // the login check above is already handling the redirect
        savedOutfits = (await res.json()).slice(0, MAX_CARDS);   // the backend sends the newest first
    } catch (err) {
        savedOutfits = [];
    }
    buildCards();
}

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
// Keyboard: Enter/Space on the front card (a keyboard click has detail 0), arrow keys to move
stack.addEventListener('click', (e) => { if (e.detail === 0 && e.target.closest('.card')?.dataset.pos === 'front') openFront(); });
stack.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') go(current + 1);
    if (e.key === 'ArrowLeft') go(current - 1);
});

loadSavedOutfits();
