const OUTFIT_TOPS = ['short_sleeve_top', 'long_sleeve_top'];
const OUTFIT_BOTTOMS = ['pants', 'shorts', 'skirt'];

function renderOutfit(stage, items) {
    stage.innerHTML = '';
    stage.classList.remove('empty');

    const pick = (categories) => items.filter(i => categories.includes(i.category));
    const makeImg = (item, className) => {
        const img = document.createElement('img');
        img.src = photoUrl(item.image_url);
        img.alt = item.category.replace(/_/g, ' ');
        img.className = className;
        img.onerror = () => { img.style.visibility = 'hidden'; };  // never show a broken-image icon
        return img;
    };

    // Main column: either a dress, or top + bottom, then shoes underneath
    const figure = document.createElement('div');
    figure.className = 'fig';
    pick(['dress']).forEach(i => figure.appendChild(makeImg(i, 'p-dress')));
    pick(OUTFIT_TOPS).forEach(i => figure.appendChild(makeImg(i, 'p-top')));
    pick(OUTFIT_BOTTOMS).forEach(i => figure.appendChild(makeImg(i, 'p-bottom')));
    pick(['shoes']).forEach(i => figure.appendChild(makeImg(i, 'p-shoes')));
    stage.appendChild(figure);

    // Side column: outerwear and accessories, only if the outfit has any
    const extras = [...pick(['outerwear']), ...pick(['accessory'])];
    if (extras.length) {
        const side = document.createElement('div');
        side.className = 'extras';
        extras.forEach(i => side.appendChild(makeImg(i, 'p-extra')));
        stage.appendChild(side);
    }
}

function showStageMessage(stage, text) {
    stage.innerHTML = '';
    stage.classList.add('empty');
    const p = document.createElement('p');
    p.textContent = text;
    stage.appendChild(p);
}
