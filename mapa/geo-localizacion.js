/* Travelity: GPS opt-in, local browser API. No coordinates are sent to our server. */
(function () {
  'use strict';
  function ready() {
    var map = window.mapa;
    if (!map || typeof L === 'undefined') return;

    var button = document.createElement('button');
    button.type = 'button';
    button.id = 'travelity-my-location';
    button.textContent = '⌖ Mi ubicación';
    button.setAttribute('aria-label', 'Mostrar mi ubicación actual en el mapa');
    button.style.cssText = 'position:fixed;right:16px;bottom:20px;z-index:1200;border:2px solid #F2B33D;border-radius:28px;padding:12px 16px;background:#101319;color:#F5F7FB;font:bold 14px system-ui;box-shadow:0 2px 12px #0008;cursor:pointer';
    document.body.appendChild(button);

    var marker = null;
    var accuracyCircle = null;
    var locating = false;
    var GEO_TEXTS = {
      es: {
        button: '⌖ Mi ubicación', locating: '⌖ Localizando…', popup: 'Tu ubicación aproximada',
        invalid: 'El navegador devolvió una ubicación no válida.',
        denied: 'Permite el acceso a la ubicación en tu navegador y vuelve a pulsar el botón.',
        timeout: 'La ubicación tardó demasiado. Comprueba que la ubicación del dispositivo esté activada y vuelve a intentarlo.',
        unavailable: 'El navegador no ha podido localizarte. Comprueba que la ubicación del dispositivo esté activada y vuelve a intentarlo.',
        unsupported: 'Este navegador no ofrece geolocalización.'
      },
      ca: {
        button: '⌖ La meva ubicació', locating: '⌖ Localitzant…', popup: 'La teva ubicació aproximada',
        invalid: 'El navegador ha retornat una ubicació no vàlida.',
        denied: "Permet l'accés a la ubicació al navegador i torna a prémer el botó.",
        timeout: 'La ubicació ha trigat massa. Comprova que la ubicació del dispositiu estigui activada i torna-ho a provar.',
        unavailable: 'El navegador no ha pogut localitzar-te. Comprova que la ubicació del dispositiu estigui activada i torna-ho a provar.',
        unsupported: 'Aquest navegador no ofereix geolocalització.'
      },
      en: {
        button: '⌖ My location', locating: '⌖ Locating…', popup: 'Your approximate location',
        invalid: 'The browser returned an invalid location.',
        denied: 'Allow location access in your browser, then press the button again.',
        timeout: 'Location took too long. Check that device location is enabled and try again.',
        unavailable: 'The browser could not locate you. Check that device location is enabled and try again.',
        unsupported: 'This browser does not offer geolocation.'
      },
      fr: {
        button: '⌖ Ma position', locating: '⌖ Localisation…', popup: 'Votre position approximative',
        invalid: 'Le navigateur a renvoyé une position invalide.',
        denied: "Autorisez l'accès à la position dans votre navigateur, puis réessayez.",
        timeout: 'La localisation a pris trop de temps. Vérifiez que la position de l’appareil est activée, puis réessayez.',
        unavailable: 'Le navigateur n’a pas pu vous localiser. Vérifiez que la position de l’appareil est activée, puis réessayez.',
        unsupported: 'Ce navigateur ne propose pas la géolocalisation.'
      },
      de: {
        button: '⌖ Mein Standort', locating: '⌖ Standort wird gesucht…', popup: 'Dein ungefährer Standort',
        invalid: 'Der Browser hat einen ungültigen Standort zurückgegeben.',
        denied: 'Erlaube den Standortzugriff im Browser und drücke die Schaltfläche erneut.',
        timeout: 'Die Standortsuche dauerte zu lange. Aktiviere die Gerätestandortbestimmung und versuche es erneut.',
        unavailable: 'Der Browser konnte deinen Standort nicht ermitteln. Aktiviere die Gerätestandortbestimmung und versuche es erneut.',
        unsupported: 'Dieser Browser bietet keine Geolokalisierung.'
      },
      it: {
        button: '⌖ La mia posizione', locating: '⌖ Ricerca posizione…', popup: 'La tua posizione approssimativa',
        invalid: 'Il browser ha restituito una posizione non valida.',
        denied: 'Consenti l’accesso alla posizione nel browser e premi di nuovo il pulsante.',
        timeout: 'La localizzazione ha impiegato troppo tempo. Attiva la posizione del dispositivo e riprova.',
        unavailable: 'Il browser non ha potuto localizzarti. Attiva la posizione del dispositivo e riprova.',
        unsupported: 'Questo browser non offre la geolocalizzazione.'
      },
      pt: {
        button: '⌖ Minha localização', locating: '⌖ Localizando…', popup: 'A sua localização aproximada',
        invalid: 'O navegador devolveu uma localização inválida.',
        denied: 'Permita o acesso à localização no navegador e prima novamente o botão.',
        timeout: 'A localização demorou demasiado. Verifique se a localização do dispositivo está ativa e tente novamente.',
        unavailable: 'O navegador não conseguiu localizá-lo. Verifique se a localização do dispositivo está ativa e tente novamente.',
        unsupported: 'Este navegador não oferece geolocalização.'
      },
      nl: {
        button: '⌖ Mijn locatie', locating: '⌖ Locatie zoeken…', popup: 'Je geschatte locatie',
        invalid: 'De browser gaf een ongeldige locatie terug.',
        denied: 'Sta locatietoegang toe in je browser en druk opnieuw op de knop.',
        timeout: 'Het ophalen van de locatie duurde te lang. Schakel de locatie van je apparaat in en probeer opnieuw.',
        unavailable: 'De browser kon je niet lokaliseren. Schakel de locatie van je apparaat in en probeer opnieuw.',
        unsupported: 'Deze browser ondersteunt geen geolocatie.'
      },
      ru: {
        button: '⌖ Моё местоположение', locating: '⌖ Определение местоположения…', popup: 'Ваше примерное местоположение',
        invalid: 'Браузер вернул недействительное местоположение.',
        denied: 'Разрешите доступ к местоположению в браузере и нажмите кнопку ещё раз.',
        timeout: 'Определение местоположения заняло слишком много времени. Включите геолокацию устройства и повторите попытку.',
        unavailable: 'Браузеру не удалось определить ваше местоположение. Включите геолокацию устройства и повторите попытку.',
        unsupported: 'Этот браузер не поддерживает геолокацию.'
      },
      ja: {
        button: '⌖ 現在地', locating: '⌖ 現在地を取得中…', popup: 'おおよその現在地',
        invalid: 'ブラウザから無効な位置情報が返されました。',
        denied: 'ブラウザで位置情報へのアクセスを許可して、もう一度ボタンを押してください。',
        timeout: '位置情報の取得に時間がかかりすぎました。端末の位置情報を有効にして再試行してください。',
        unavailable: 'ブラウザで位置情報を取得できませんでした。端末の位置情報を有効にして再試行してください。',
        unsupported: 'このブラウザは位置情報に対応していません。'
      },
      zh: {
        button: '⌖ 我的位置', locating: '⌖ 正在定位…', popup: '您的大致位置',
        invalid: '浏览器返回的位置无效。',
        denied: '请在浏览器中允许访问位置信息，然后再次点击按钮。',
        timeout: '获取位置超时。请确认设备定位已开启，然后重试。',
        unavailable: '浏览器无法确定您的位置。请确认设备定位已开启，然后重试。',
        unsupported: '此浏览器不支持地理定位。'
      },
      'zh-Hant': {
        button: '⌖ 我的位置', locating: '⌖ 正在定位…', popup: '您的大約位置',
        invalid: '瀏覽器傳回的位置無效。',
        denied: '請在瀏覽器中允許存取位置，然後再次按下按鈕。',
        timeout: '取得位置逾時。請確認裝置定位已開啟，然後重試。',
        unavailable: '瀏覽器無法判定您的位置。請確認裝置定位已開啟，然後重試。',
        unsupported: '此瀏覽器不支援地理定位。'
      }
    };

    function getLanguage() {
      var select = document.getElementById('selIdiomaMapa');
      var documentLanguage = document.documentElement && document.documentElement.lang;
      var language = (select && select.value) || window.idiomaMapa || documentLanguage || 'es';
      return GEO_TEXTS[language] ? language : 'es';
    }

    function getTexts() {
      return GEO_TEXTS[getLanguage()] || GEO_TEXTS.es;
    }

    var attempts = [
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 120000 },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
    ];

    function resetButton() {
      locating = false;
      button.disabled = false;
      button.textContent = getTexts().button;
    }

    function updateLanguage() {
      var texts = getTexts();
      button.textContent = locating ? texts.locating : texts.button;
      if (marker && marker.setPopupContent) marker.setPopupContent(texts.popup);
    }

    function showPosition(position) {
      var lat = position.coords.latitude;
      var lon = position.coords.longitude;
      if (!isFinite(lat) || !isFinite(lon)) {
        resetButton();
        window.alert(getTexts().invalid);
        return;
      }
      if (marker) map.removeLayer(marker);
      if (accuracyCircle) map.removeLayer(accuracyCircle);
      marker = L.circleMarker([lat, lon], { radius: 9, color: '#ffffff', weight: 3, fillColor: '#2389ff', fillOpacity: 1 }).addTo(map).bindPopup(getTexts().popup);
      var accuracy = Number(position.coords.accuracy);
      if (isFinite(accuracy) && accuracy > 0) {
        accuracyCircle = L.circle([lat, lon], { radius: Math.min(accuracy, 10000), color: '#2389ff', weight: 1, fillOpacity: 0.08 }).addTo(map);
      }
      map.setView([lat, lon], Math.max(map.getZoom(), 15));
      resetButton();
      marker.openPopup();
    }

    function showError(error) {
      var texts = getTexts();
      var reason;
      if (error && error.code === 1) {
        reason = texts.denied;
      } else if (error && error.code === 3) {
        reason = texts.timeout;
      } else {
        reason = texts.unavailable;
      }
      resetButton();
      window.alert(reason);
    }

    function locate(attempt) {
      navigator.geolocation.getCurrentPosition(showPosition, function (error) {
        if (attempt + 1 < attempts.length && error && (error.code === 2 || error.code === 3)) {
          locate(attempt + 1);
          return;
        }
        showError(error);
      }, attempts[attempt]);
    }

    button.addEventListener('click', function () {
      if (locating) return;
      if (!navigator.geolocation) {
        window.alert(getTexts().unsupported);
        return;
      }
      locating = true;
      button.disabled = true;
      button.textContent = getTexts().locating;
      locate(0);
    });

    var languageSelect = document.getElementById('selIdiomaMapa');
    if (languageSelect) languageSelect.addEventListener('change', updateLanguage);
    updateLanguage();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();

