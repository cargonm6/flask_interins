document.addEventListener("DOMContentLoaded", function () {
  const input = document.getElementById("busqueda");
  const lista = document.getElementById("sugerencias");
  const loader = document.getElementById("loader");

  let debounceTimeout = null;

  input.addEventListener("input", function () {
    const query = input.value.trim();

    if (debounceTimeout) {
      clearTimeout(debounceTimeout);
    }

    if (query.length < 2) {
      lista.innerHTML = "";
      loader.classList.remove("active");  // cambiar aquí
      return;
    }

    debounceTimeout = setTimeout(() => {
      loader.classList.add("active");  // cambiar aquí

      fetch(`/autocomplete?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
          lista.innerHTML = "";
          loader.classList.remove("active");  // y aquí

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
          loader.classList.remove("active");  // y aquí también
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
    // Borrar cookies
    document.cookie.split(";").forEach(function(c) {
      document.cookie = c
        .replace(/^ +/, "") // Quitar espacios
        .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
    });

    // Borrar localStorage y sessionStorage (opcional)
    localStorage.clear();
    sessionStorage.clear();

    // Recargar la página
    location.reload();
}