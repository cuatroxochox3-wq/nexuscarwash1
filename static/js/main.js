/* NEXUS CAR WASH - Interacciones de interfaz (sin dependencias) */
document.addEventListener("DOMContentLoaded", () => {
  // Menú móvil
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.querySelectorAll("a").forEach((link) =>
      link.addEventListener("click", () => nav.classList.remove("is-open"))
    );
  }

  // Mensajes flash: cierre manual y automático
  document.querySelectorAll("[data-flash]").forEach((alert) => {
    const close = () => {
      alert.classList.add("is-hiding");
      setTimeout(() => alert.remove(), 300);
    };
    const btn = alert.querySelector("[data-flash-close]");
    if (btn) btn.addEventListener("click", close);
    setTimeout(close, 7000);
  });

  // Mostrar / ocultar contraseña
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.togglePassword);
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.innerHTML = show ? '<i class="fa-solid fa-eye-slash"></i>' : '<i class="fa-solid fa-eye"></i>';
    });
  });

  // Generador de contraseñas seguras para el administrador
  document.querySelectorAll("[data-generate-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.generatePassword);
      if (!input) return;
      const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#$%";
      let pwd = "";
      for (let i = 0; i < 10; i++) {
        pwd += chars.charAt(Math.floor(Math.random() * chars.length));
      }
      input.value = pwd;
      input.type = "text";
      const toggleBtn = document.querySelector(`[data-toggle-password="${btn.dataset.generatePassword}"]`);
      if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
      input.focus();
      input.select();
    });
  });

  // Confirmación antes de acciones destructivas
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Filtro instantáneo de la tabla de clientes
  const filterInput = document.querySelector("[data-table-filter]");
  if (filterInput) {
    const table = document.querySelector(filterInput.dataset.tableFilter);
    const emptyMsg = document.querySelector("[data-filter-empty]");
    filterInput.addEventListener("input", () => {
      const query = filterInput.value.trim().toLowerCase();
      let visible = 0;
      table.querySelectorAll("tbody tr[data-search]").forEach((row) => {
        const match = row.dataset.search.includes(query);
        row.hidden = !match;
        if (match) visible += 1;
      });
      if (emptyMsg) emptyMsg.hidden = visible !== 0;
    });
  }

  // Previsualización de fotos de servicios
  const photoInput = document.querySelector("[data-photo-input]");
  if (photoInput) {
    const img = document.querySelector("[data-photo-img]");
    const empty = document.querySelector("[data-photo-empty]");
    const nameLabel = document.querySelector("[data-photo-name]");
    photoInput.addEventListener("change", () => {
      const file = photoInput.files && photoInput.files[0];
      if (file) {
        if (nameLabel) nameLabel.textContent = `Archivo seleccionado: ${file.name} (${Math.round(file.size / 1024)} KB)`;
        const reader = new FileReader();
        reader.onload = (e) => {
          if (img) {
            img.src = e.target.result;
            img.hidden = false;
          }
          if (empty) empty.hidden = true;
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Comportamiento dinámico del formulario de fidelidad en la ficha de cliente
  const loyaltyKind = document.querySelector("[data-loyalty-kind]");
  if (loyaltyKind) {
    const pointsInput = document.querySelector("[data-loyalty-points]");
    const hint = document.querySelector("[data-loyalty-hint]");
    const defaultVisitPoints = loyaltyKind.dataset.visitPoints || "50";

    const updateLoyaltyState = () => {
      const val = loyaltyKind.value;
      if (val === "visit") {
        if (pointsInput) pointsInput.value = defaultVisitPoints;
        if (hint) hint.textContent = `Visita: suma ${defaultVisitPoints} puntos y agrega 1 visita al contador.`;
      } else if (val === "bonus") {
        if (hint) hint.textContent = "Puntos extra: suma puntos sin alterar el contador de visitas.";
      } else if (val === "redeem") {
        if (hint) hint.textContent = "Canje: resta la cantidad indicada de puntos del saldo del cliente.";
      } else if (val === "adjust") {
        if (hint) hint.textContent = "Ajuste manual: ingresa un valor positivo o negativo para corregir el saldo.";
      }
    };
    loyaltyKind.addEventListener("change", updateLoyaltyState);
    updateLoyaltyState();
  }
});
