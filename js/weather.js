/* weather.js - the live weather tile on the dashboard.
   Load it AFTER common.js. Uses Open-Meteo (free, no API key). */

const wxTile = document.getElementById('wxTile');
const wxIcon = document.getElementById('wxIcon');
const wxTemp = document.getElementById('wxTemp');
const wxDesc = document.getElementById('wxDesc');
let weatherReady = false;

// Turns Open-Meteo's weather code into an icon, a label and a tile colour
function describeWeather(code, isDay) {
    if (code === 0) return isDay ? { icon: '☀️', label: 'Clear', theme: 'clear' } : { icon: '🌙', label: 'Clear night', theme: 'night' };
    if (code <= 2)  return isDay ? { icon: '⛅', label: 'Partly cloudy', theme: 'cloud' } : { icon: '☁️', label: 'Partly cloudy', theme: 'night' };
    if (code === 3) return { icon: '☁️', label: 'Overcast', theme: 'cloud' };
    if (code === 45 || code === 48) return { icon: '🌫️', label: 'Foggy', theme: 'fog' };
    if (code >= 51 && code <= 57) return { icon: '🌦️', label: 'Drizzle', theme: 'rain' };
    if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return { icon: '🌧️', label: 'Rain', theme: 'rain' };
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return { icon: '❄️', label: 'Snow', theme: 'snow' };
    if (code >= 95) return { icon: '⛈️', label: 'Thunderstorm', theme: 'storm' };
    return { icon: '☁️', label: 'Cloudy', theme: 'cloud' };
}

function showWeatherProblem(message) {
    weatherReady = false;
    wxTemp.textContent = '--';
    wxDesc.textContent = message;
}

function loadWeather() {
    // The Location switch on the Settings page turns this off
    if (localStorage.getItem('styleme_location') === 'off') return showWeatherProblem('Location is off in Settings');

    wxDesc.textContent = 'Getting weather...';
    if (!navigator.geolocation) return showWeatherProblem('Location not supported');

    navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
            const { latitude, longitude } = pos.coords;
            const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code,is_day&timezone=auto`;
            const data = await (await fetch(url)).json();
            const c = data.current;
            const info = describeWeather(c.weather_code, c.is_day === 1);
            const temp = Math.round(c.temperature_2m);

            wxIcon.textContent = info.icon;
            wxTemp.textContent = temp + '°C';
            wxDesc.textContent = info.label;
            wxTile.dataset.theme = info.theme;
            weatherReady = true;

            // The weather outfit page can read this later
            sessionStorage.setItem('styleme_weather', JSON.stringify({ temp, code: c.weather_code, label: info.label }));
        } catch (err) {
            showWeatherProblem('Weather unavailable. Tap to retry');
        }
    }, () => showWeatherProblem('Tap to allow location'), { timeout: 10000, maximumAge: 600000 });
}

// If there is no weather yet, tapping the tile retries instead of leaving the page
wxTile.addEventListener('click', (e) => { if (!weatherReady) { e.preventDefault(); loadWeather(); } });
loadWeather();
