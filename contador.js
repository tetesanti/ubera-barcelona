/* Travelity: contador total compartido de aperturas reales de página. */
(function () {
  'use strict';

  var ENDPOINT = 'https://abacus.jasoncameron.dev/hit/travelity-es/total';
  var output = document.getElementById('total-page-views');
  if (!output || !window.fetch) return;

  fetch(ENDPOINT, {
    method: 'GET',
    mode: 'cors',
    cache: 'no-store',
    credentials: 'omit',
    keepalive: true,
    referrerPolicy: 'no-referrer'
  })
    .then(function (response) {
      if (!response.ok) throw new Error('counter request failed');
      return response.json();
    })
    .then(function (data) {
      var value = Number(data && data.value);
      if (!isFinite(value) || value < 0) throw new Error('invalid counter value');
      output.textContent = value.toLocaleString('es-ES');
      output.setAttribute('data-counter-status', 'ok');
    })
    .catch(function () {
      output.textContent = 'No disponible';
      output.setAttribute('data-counter-status', 'error');
    });
})();
