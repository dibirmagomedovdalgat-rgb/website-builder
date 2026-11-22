(() => {
  // Вспомогательная функция для toast-уведомлений
  function showToast(message, isError = false) {
    let container = document.getElementById("store-toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "store-toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast ${isError ? "toast-error" : "toast-success"}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add("toast-hide");
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // Извлечение понятного текста ошибки из ответа FastAPI
  async function extractErrorMessage(response) {
    try {
      const data = await response.json();
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) {
        return data.detail.map((e) => e.msg).join("; ");
      }
      if (data.message) return data.message;
    } catch (_) {}
    return `Ошибка сервера (${response.status})`;
  }

  // Универсальный вызов API
  async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
    });

    if (response.status === 401) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?next=${next}`;
      throw new Error("Требуется авторизация");
    }

    if (!response.ok) {
      const msg = await extractErrorMessage(response);
      throw new Error(msg);
    }

    return response.json();
  }

  // 1. Обработка кнопок "В корзину" / "+" / "-"
  document.addEventListener("click", async (e) => {
    const addBtn = e.target.closest("[data-action='add-to-cart']");
    if (addBtn) {
      e.preventDefault();
      const productId = addBtn.dataset.productId;
      const qtyInput = document.getElementById("detail-qty-input");
      const quantity = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;

      addBtn.disabled = true;
      try {
        const res = await apiRequest(
          `/basket/add?product_id=${encodeURIComponent(productId)}&quantity=${encodeURIComponent(quantity)}`,
          { method: "POST" }
        );
        showToast(res.message || "Товар добавлен в корзину");

        // Если мы на странице корзины — перезагружаем для пересчёта сумм
        if (window.location.pathname === "/cart") {
          window.location.reload();
          return;
        }

        // Обновляем счётчик в шапке и бейдж на карточке
        const badge = document.getElementById("header-cart-count");
        if (badge) {
          const current = parseInt(badge.textContent, 10) || 0;
          badge.textContent = current + quantity;
        }
        const cardNote = document.querySelector(`[data-in-cart-id="${productId}"]`);
        if (cardNote) {
          const prev = parseInt(cardNote.dataset.qty, 10) || 0;
          const nextQty = prev + quantity;
          cardNote.dataset.qty = nextQty;
          cardNote.textContent = `В корзине: ${nextQty} шт.`;
          cardNote.hidden = false;
        }
      } catch (err) {
        if (err.message !== "Требуется авторизация") {
          showToast(err.message, true);
        }
      } finally {
        addBtn.disabled = false;
      }
      return;
    }

    const decBtn = e.target.closest("[data-action='decrease-cart']");
    if (decBtn) {
      e.preventDefault();
      const productId = decBtn.dataset.productId;
      decBtn.disabled = true;
      try {
        const res = await apiRequest(
          `/basket/decrease?product_id=${encodeURIComponent(productId)}&quantity=1`,
          { method: "POST" }
        );
        showToast(res.message || "Количество уменьшено");
        window.location.reload();
      } catch (err) {
        showToast(err.message, true);
        decBtn.disabled = false;
      }
      return;
    }

    // 2. Отмена заказа
    const cancelBtn = e.target.closest("[data-action='cancel-order']");
    if (cancelBtn) {
      e.preventDefault();
      const orderId = cancelBtn.dataset.orderId;
      if (!confirm(`Вы уверены, что хотите отменить заказ №${orderId}?`)) return;

      cancelBtn.disabled = true;
      try {
        const res = await apiRequest(`/orders/${encodeURIComponent(orderId)}/cancel`, {
          method: "POST",
        });
        showToast(res.message || "Заказ отменён");
        setTimeout(() => window.location.reload(), 700);
      } catch (err) {
        showToast(err.message, true);
        cancelBtn.disabled = false;
      }
      return;
    }

    // 3. Переключение миниатюр в галерее товара
    const thumb = e.target.closest("[data-gallery-src]");
    if (thumb) {
      const mainImg = document.getElementById("main-product-image");
      if (mainImg) {
        mainImg.src = thumb.dataset.gallerySrc;
        document.querySelectorAll("[data-gallery-src]").forEach((el) => el.classList.remove("active"));
        thumb.classList.add("active");
      }
    }
  });

  // 4. Форма входа (/login)
  const loginForm = document.getElementById("store-login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = loginForm.querySelector("button[type='submit']");
      const errorBox = document.getElementById("form-error");
      if (errorBox) errorBox.textContent = "";

      const formData = new FormData(loginForm);
      const payload = {
        email: formData.get("email"),
        password: formData.get("password"),
      };

      submitBtn.disabled = true;
      try {
        await apiRequest("/users/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const nextUrl = loginForm.dataset.next || "/";
        window.location.href = nextUrl;
      } catch (err) {
        if (errorBox) errorBox.textContent = err.message;
        else showToast(err.message, true);
        submitBtn.disabled = false;
      }
    });
  }

  // 5. Форма регистрации (/register)
  const registerForm = document.getElementById("store-register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = registerForm.querySelector("button[type='submit']");
      const errorBox = document.getElementById("form-error");
      if (errorBox) errorBox.textContent = "";

      const formData = new FormData(registerForm);
      const phone = (formData.get("phone") || "").trim();
      const bio = (formData.get("bio") || "").trim();

      const payload = {
        name: formData.get("name"),
        email: formData.get("email"),
        password: formData.get("password"),
        phone: phone || null,
        bio: bio || null,
      };

      submitBtn.disabled = true;
      try {
        await apiRequest("/users/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        // Сразу логиним пользователя после успешной регистрации
        await apiRequest("/users/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: payload.email, password: payload.password }),
        });
        window.location.href = "/";
      } catch (err) {
        if (errorBox) errorBox.textContent = err.message;
        else showToast(err.message, true);
        submitBtn.disabled = false;
      }
    });
  }

  // 6. Форма оформления заказа (/cart)
  const checkoutForm = document.getElementById("store-checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = checkoutForm.querySelector("button[type='submit']");
      const errorBox = document.getElementById("checkout-error");
      if (errorBox) errorBox.textContent = "";

      const formData = new FormData(checkoutForm);
      const phone = (formData.get("phone") || "").trim();
      const address = (formData.get("delivery_address") || "").trim();
      const comment = (formData.get("comment") || "").trim();

      const payload = {
        phone: phone || null,
        delivery_address: address || "Самовывоз",
        comment: comment || null,
      };

      submitBtn.disabled = true;
      try {
        const order = await apiRequest("/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast(`Заказ №${order.id} успешно оформлен!`);
        setTimeout(() => {
          window.location.href = "/orders";
        }, 700);
      } catch (err) {
        if (errorBox) errorBox.textContent = err.message;
        else showToast(err.message, true);
        submitBtn.disabled = false;
      }
    });
  }


  // 7. Профиль: переключение режима и сохранение (/profile)
  document.addEventListener("click", (e) => {
    const toggleBtn = e.target.closest("#toggle-edit-profile");
    if (toggleBtn) {
      const form = document.getElementById("store-profile-form");
      const view = document.getElementById("profile-view-mode");
      if (form && view) {
        view.hidden = true;
        view.style.display = "none";
        form.hidden = false;
        form.style.display = "block";
        toggleBtn.hidden = true;
        toggleBtn.style.display = "none";
      }
      return;
    }

    const cancelBtn = e.target.closest("#cancel-edit-profile");
    if (cancelBtn) {
      const form = document.getElementById("store-profile-form");
      const view = document.getElementById("profile-view-mode");
      const toggle = document.getElementById("toggle-edit-profile");
      if (form && view) {
        form.hidden = true;
        form.style.display = "none";
        view.hidden = false;
        view.style.display = "block";
        if (toggle) {
          toggle.hidden = false;
          toggle.style.display = "inline-flex";
        }
        const errBox = document.getElementById("profile-error");
        if (errBox) errBox.textContent = "";
      }
    }
  });

  document.addEventListener("submit", async (e) => {
    const profileForm = e.target.closest("#store-profile-form");
    if (!profileForm) return;

    e.preventDefault();
    const submitBtn = profileForm.querySelector("button[type='submit']");
    const errorBox = document.getElementById("profile-error");
    if (errorBox) errorBox.textContent = "";

    const formData = new FormData(profileForm);
    const payload = {
      name: (formData.get("name") || "").trim(),
      email: (formData.get("email") || "").trim(),
      phone: (formData.get("phone") || "").trim() || null,
      bio: (formData.get("bio") || "").trim() || null,
    };

    submitBtn.disabled = true;
    try {
      const updatedUser = await apiRequest("/users/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      showToast("Профиль успешно обновлён!");

      document.getElementById("view-prof-name").textContent = updatedUser.name;
      document.getElementById("view-prof-email").textContent = updatedUser.email;
      document.getElementById("view-prof-phone").textContent =
        updatedUser.phone || "Не указан (заполнится при первом заказе)";

      const bioWrap = document.getElementById("view-prof-bio-wrap");
      const bioEl = document.getElementById("view-prof-bio");
      if (updatedUser.bio) {
        bioEl.textContent = updatedUser.bio;
        bioWrap.hidden = false;
      } else {
        bioWrap.hidden = true;
      }

      const headerProfileLink = document.querySelector(".nav-links a[href='/profile']");
      if (headerProfileLink) headerProfileLink.textContent = updatedUser.name;

      const profileView = document.getElementById("profile-view-mode");
      const toggleEditBtn = document.getElementById("toggle-edit-profile");
      profileForm.hidden = true;
      profileForm.style.display = "none";
      if (profileView) {
        profileView.hidden = false;
        profileView.style.display = "block";
      }
      if (toggleEditBtn) {
        toggleEditBtn.hidden = false;
        toggleEditBtn.style.display = "inline-flex";
      }
    } catch (err) {
      if (errorBox) errorBox.textContent = err.message;
      else showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
