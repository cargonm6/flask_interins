document.addEventListener("DOMContentLoaded", function() {
  const input = document.getElementById("busqueda");
  const lista = document.getElementById("sugerencias");
  const loader = document.getElementById("loader");

  let debounceTimeout = null;

  input.addEventListener("input", function() {
    const query = input.value.trim();

    if (debounceTimeout) {
      clearTimeout(debounceTimeout);
    }

    if (query.length < 2) {
      lista.innerHTML = "";
      loader.classList.remove("active");
      return;
    }

    debounceTimeout = setTimeout(() => {
      loader.classList.add("active");

      fetch(`/autocomplete?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
          lista.innerHTML = "";
          loader.classList.remove("active");

          data.forEach(item => {
            const li = document.createElement("li");
            li.textContent = item;
            li.style.cursor = "pointer";
            li.style.padding = "4px";
            li.addEventListener("click", () => {
              input.value = item;
              lista.innerHTML = "";
            });
            lista.appendChild(li);
          });
        })
        .catch(() => {
          loader.classList.remove("active");
        });
    }, 500);
  });

  input.addEventListener("blur", () => setTimeout(() => lista.innerHTML = "", 100));
});

function download_img(elemento) {
  // Obtener la ruta completa
  const url = elemento.src;

  // Extraer solo el nombre del archivo
  const nombreArchivo = url.substring(url.lastIndexOf('/') + 1);

  // Crear enlace temporal
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombreArchivo;
  enlace.click();
}

function reset_page() {
  // Si tu app realmente usa cookies personalizadas
  if (document.cookie) {
    document.cookie.split(";").forEach(function(c) {
      document.cookie = c
        .replace(/^ +/, "")
        .replace(/=.*/, "=;expires=" + new Date(0).toUTCString() + ";path=/");
    });
  }

  if (localStorage) localStorage.clear();
  if (sessionStorage) sessionStorage.clear();

  location.href = "/";
}

function download_img() {
  const graphDiv = document.querySelector('#plotly-container div.js-plotly-plot');
  if (graphDiv) {
    Plotly.downloadImage(graphDiv, {
      format: 'png',
      filename: 'grafica',
      width: 1000,
      height: 700,
      scale: 1
    });
  }
}

window.addEventListener('resize', function() {
  const plotlyGraph = document.getElementById('plotly-container');
  if (plotlyGraph) {
    var aspectRatio = 16 / 9;
    var newHeight = plotlyGraph.offsetWidth / aspectRatio;
    plotlyGraph.style.height = newHeight + 'px';
  }
});