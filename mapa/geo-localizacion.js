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
    var attempts = [
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 120000 },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
    ];

    function resetButton() {
      locating = false;
      button.disabled = false;
      button.textContent = '⌖ Mi ubicación';
    }

    function showPosition(position) {
      var lat = position.coords.latitude;
      var lon = position.coords.longitude;
      if (!isFinite(lat) || !isFinite(lon)) {
        resetButton();
        window.alert('El navegador devolvió una ubicación no válida.');
        return;
      }
      if (marker) map.removeLayer(marker);
      if (accuracyCircle) map.removeLayer(accuracyCircle);
      marker = L.circleMarker([lat, lon], { radius: 9, color: '#ffffff', weight: 3, fillColor: '#2389ff', fillOpacity: 1 }).addTo(map).bindPopup('Tu ubicación aproximada');
      var accuracy = Number(position.coords.accuracy);
      if (isFinite(accuracy) && accuracy > 0) {
        accuracyCircle = L.circle([lat, lon], { radius: Math.min(accuracy, 10000), color: '#2389ff', weight: 1, fillOpacity: 0.08 }).addTo(map);
      }
      map.setView([lat, lon], Math.max(map.getZoom(), 15));
      resetButton();
      marker.openPopup();
    }

    function showError(error) {
      var reason;
      if (error && error.code === 1) {
        reason = 'Permite el acceso a la ubicación en tu navegador y vuelve a pulsar el botón.';
      } else if (error && error.code === 3) {
        reason = 'La ubicación tardó demasiado. Comprueba que la ubicación del dispositivo esté activada y vuelve a intentarlo.';
      } else {
        reason = 'El navegador no ha podido localizarte. Comprueba que la ubicación del dispositivo esté activada y vuelve a intentarlo.';
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
        window.alert('Este navegador no ofrece geolocalización.');
        return;
      }
      locating = true;
      button.disabled = true;
      button.textContent = '⌖ Localizando…';
      locate(0);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();

