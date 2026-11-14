const CATEGORY_OPTIONS = [
    ['short_sleeve_top', 'Short sleeve top'],
    ['long_sleeve_top', 'Long sleeve top'],
    ['t_shirt', 'T-shirt'],
    ['button_up_shirt', 'Button-up shirt'],
    ['blouse', 'Blouse'],
    ['tank_top', 'Tank Top'],
    ['singlet', 'Singlet'],
    ['jumper', 'Jumper'],
    ['hoodie', 'Hoodie'],
    ['sweatshirt', 'Sweatshirt'],    
    ['pants', 'Pants'],
    ['jeans', 'Jeans'],
    ['shorts', 'Shorts'],
    ['skirt', 'Skirt'],
    ['dress', 'Dress'],
    ['outerwear', 'Outerwear'],
    ['jacket', 'Jacket'],
    ['coat', 'Coat'],
    ['vest', 'Vest'],
    ['shoes', 'Shoes'],
    ['slippers', 'Slippers'],
    ['boots', 'Boots'],
    ['heels', 'Heels'],
    ['flats', 'Flats'],
    ['sandals', 'Sandals'],
    ['trainers', 'Trainers'],
    ['hat', 'Hat'],
    ['sunglasses', 'Sunglasses'],
    ['glasses', 'Glasses'],
    ['necklace', 'Necklace'],
    ['watch', 'Watch'],
    ['bracelet', 'Bracelet'],
    ['ring', 'Ring'],
    ['earrings', 'Earrings'],
    ['scarf', 'Scarf'],
    ['gloves', 'Gloves'],
    ['belt', 'Belt'],
    ['bag', 'Bag'],
    ['tie', 'Tie'],
    ['accessory', 'Other accessory'],
];

const COLOUR_OPTIONS = [
    'black', 'white', 'grey', 'beige', 'brown', 'red', 'orange',
    'yellow', 'green', 'blue', 'navy', 'purple', 'pink', 'multicolour',
].map(c => [c, c[0].toUpperCase() + c.slice(1)]);

const PATTERN_OPTIONS = [
    ['solid', 'Solid'], ['striped', 'Striped'], ['checked', 'Checked'],
    ['floral', 'Floral'], ['spotted', 'Spotted'], ['graphic', 'Graphic'], ['other', 'Other'],
    ['plaid', 'Plaid'], ['paisley', 'Paisley'], ['camouflage', 'Camouflage'], ['animal_print', 'Animal print'],
    ['tie_dye', 'Tie-dye'], ['geometric', 'Geometric'], ['textured', 'Textured'], ['denim', 'Denim'],
    ['lace', 'Lace'], ['logo', 'Logo'],
];

const SEASON_OPTIONS = [
    ['spring_summer', 'Spring/Summer'],
    ['autumn_winter', 'Autumn/Winter'],
];

// How dressy an item is.
const ITEM_OCCASION_OPTIONS = [
    ['casual', 'Casual'], ['smart', 'Smart'], ['formal', 'Formal'], ['sporty', 'Sporty'],
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
