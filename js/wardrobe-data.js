const CATEGORY_OPTIONS = [
    ['short_sleeve_top', 'Short sleeve top'],
    ['long_sleeve_top', 'Long sleeve top'],
    ['pants', 'Pants'],
    ['shorts', 'Shorts'],
    ['skirt', 'Skirt'],
    ['dress', 'Dress'],
    ['outerwear', 'Outerwear'],
    ['shoes', 'Shoes'],
    ['accessory', 'Accessory'],
];

const COLOUR_OPTIONS = [
    'black', 'white', 'grey', 'beige', 'brown', 'red', 'orange',
    'yellow', 'green', 'blue', 'navy', 'purple', 'pink', 'multicolour',
].map(c => [c, c[0].toUpperCase() + c.slice(1)]);

const PATTERN_OPTIONS = [
    ['solid', 'Solid'], ['striped', 'Striped'], ['checked', 'Checked'],
    ['floral', 'Floral'], ['spotted', 'Spotted'], ['graphic', 'Graphic'], ['other', 'Other'],
];

const SEASON_OPTIONS = [
    ['spring_summer', 'Spring/Summer'],
    ['autumn_winter', 'Autumn/Winter'],
];

// Fills a <select> with [value, label] pairs and selects the current one.
function fillSelect(select, options, currentValue) {
    select.innerHTML = '';
    options.forEach(([value, label]) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = label;
        if (value === currentValue) opt.selected = true;
        select.appendChild(opt);
    });
}
