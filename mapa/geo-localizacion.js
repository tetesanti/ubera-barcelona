/* Travelity: GPS opt-in, local browser API. No coordinates are sent to our server. */
(function () {
  'use strict';
  function ready() {
    var map = window.mapa;
    if (!map || typeof L === 'undefined' || !navigator.geolocation) return;

    var button = document.createElement('button');
    button.type = 'button';
    button.id = 'travelity-my-location';
    button.textContent = '⌖ Mi ubicación';
    button.setAttribute('aria-label', 'Mostrar mi ubicación actual en el mapa');
    button.style.cssText = 'position:fixed;right:16px;bottom:20px;z-index:1200;border:2px solid #F2B33D;border-radius:28px;padding:12px 16px;background:#101319;color:#F5F7FB;font:bold 14px system-ui;box-shadow:0 2px 12px #0008;cursor:pointer';
    document.body.appendChild(button);

    var marker = null;
    var accuracyCircle = null;
    button.addEventListener('click', function () {
      button.disabled = true;
      button.textContent = '⌖ Localizando…';
      navigator.geolocation.getCurrentPosition(function (position) {
        var lat = position.coords.latitude;
        var lon = position.coords.longitude;
        if (!isFinite(lat) || !isFinite(lon)) { button.disabled = false; button.textContent = '⌖ Mi ubicación'; return; }
        if (marker) map.removeLayer(marker);
        if (accuracyCircle) map.removeLayer(accuracyCircle);
        marker = L.circleMarker([lat, lon], { radius: 9, color: '#ffffff', weight: 3, fillColor: '#2389ff', fillOpacity: 1 }).addTo(map).bindPopup('Tu ubicación aproximada');
        accuracyCircle = L.circle([lat, lon], { radius: Math.min(position.coords.accuracy || 0, 10000), color: '#2389ff', weight: 1, fillOpacity: 0.08 }).addTo(map);
        map.setView([lat, lon], Math.max(map.getZoom(), 15));
        button.disabled = false;
        button.textContent = '⌖ Mi ubicación';
      }, function (error) {
        button.disabled = false;
        button.textContent = '⌖ Mi ubicación';
        var reason = error.code === 1 ? 'Permite el acceso a la ubicación en tu navegador.' : 'No se pudo obtener tu ubicación. Inténtalo de nuevo.';
        window.alert(reason);
      }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();

