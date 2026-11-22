// Подтверждение удаления
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".js-confirm-form").forEach((form) => {
        form.addEventListener("submit", (e) => {
            const message = form.dataset.confirm || "Вы уверены?";
            if (!window.confirm(message)) {
                e.preventDefault();
            }
        });
    });

const previewInput = document.getElementById("previewInput");
const previewThumb = document.getElementById("previewThumb");

if (previewInput && previewThumb) {
    previewInput.addEventListener("change", () => {
        previewThumb.replaceChildren();
        const file = previewInput.files && previewInput.files[0];
        if (!file || !file.type.startsWith("image/")) return;

        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        img.alt = "Предпросмотр";
        img.onload = () => URL.revokeObjectURL(img.src);
        previewThumb.appendChild(img);
    });
}

const galleryInput = document.getElementById("galleryInput");
const galleryThumbs = document.getElementById("galleryThumbs");

if (galleryInput && galleryThumbs) {
    const galleryStore = new DataTransfer();

    function syncAndRenderGallery() {
        galleryInput.files = galleryStore.files;
        galleryThumbs.replaceChildren();

        Array.from(galleryStore.files).forEach((file, index) => {
            const wrap = document.createElement("div");
            wrap.className = "preview-item";

            const img = document.createElement("img");
            img.src = URL.createObjectURL(file);
            img.alt = file.name;
            img.onload = () => URL.revokeObjectURL(img.src);

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "preview-remove";
            removeBtn.title = "Убрать фото";
            removeBtn.textContent = "×";
            removeBtn.addEventListener("click", () => {
                const updated = new DataTransfer();
                Array.from(galleryStore.files).forEach((f, i) => {
                    if (i !== index) updated.items.add(f);
                });
                galleryStore.items.clear();
                Array.from(updated.files).forEach((f) => galleryStore.items.add(f));
                syncAndRenderGallery();
            });

            wrap.appendChild(img);
            wrap.appendChild(removeBtn);
            galleryThumbs.appendChild(wrap);
        });
    }

    galleryInput.addEventListener("change", () => {
        const newFiles = Array.from(galleryInput.files || []);
        newFiles.forEach((file) => {
            if (!file.type.startsWith("image/")) return;
            // Защита от случайного дубликата того же файла
            const isDuplicate = Array.from(galleryStore.files).some(
                (f) => f.name === file.name && f.size === file.size
            );
            if (!isDuplicate) {
                galleryStore.items.add(file);
            }
        });
        syncAndRenderGallery();
    });
}
// Поиск и фильтр по категории
const searchInput = document.getElementById("liveSearchInput");
const catSelect = document.getElementById("liveCategoryFilter");
const rows = Array.from(document.querySelectorAll(".product-row"));
const emptyRow = document.getElementById("emptySearchRow");
const countSpan = document.getElementById("visibleCount");
const resetBtn = document.getElementById("resetFilterBtn");

function filterProducts() {
    const query = (searchInput.value || "").trim().toLowerCase();
    const selectedCat = catSelect.value;
    let visible = 0;

    rows.forEach((row) => {
        const title = (row.dataset.title || "").toLowerCase();
        const rowCat = row.dataset.catId || "";
        const matchesTitle = !query || title.includes(query);
        const matchesCat = !selectedCat || rowCat === selectedCat;

        if (matchesTitle && matchesCat) {
            row.style.display = "";
            visible++;
        } else {
            row.style.display = "none";
        }
    });

    if (countSpan) countSpan.textContent = String(visible);
    if (emptyRow) emptyRow.style.display = visible === 0 ? "" : "none";
    if (resetBtn) resetBtn.style.display = (query || selectedCat) ? "" : "none";
}

if (searchInput && catSelect) {
    searchInput.addEventListener("input", filterProducts);
    catSelect.addEventListener("change", filterProducts);
}

const flashAlert = document.getElementById("flashAlert");
if (flashAlert) {
    setTimeout(() => {
        flashAlert.style.transition = "opacity 0.4s";
        flashAlert.style.opacity = "0";
        setTimeout(() => flashAlert.remove(), 400);
    }, 4000);

    const url = new URL(window.location.href);
    if (url.searchParams.has("msg")) {
        url.searchParams.delete("msg");
        window.history.replaceState({}, "", url.toString());
    }
}
});

const lightbox = document.getElementById("imageLightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxDownload = document.getElementById("lightboxDownload");
const lightboxClose = document.getElementById("lightboxClose");

if (lightbox && lightboxImg && lightboxDownload && lightboxClose) {
    function openLightbox(src) {
        lightboxImg.src = src;
        lightboxDownload.href = src;
        const fileName = src.split("/").pop() || "image.webp";
        lightboxDownload.setAttribute("download", fileName);
        lightbox.classList.add("open");
        lightbox.setAttribute("aria-hidden", "false");
    }

    function closeLightbox() {
        lightbox.classList.remove("open");
        lightbox.setAttribute("aria-hidden", "true");
        lightboxImg.src = "";
    }

    document.querySelectorAll(".js-lightbox-img").forEach((img) => {
        img.addEventListener("click", () => openLightbox(img.src));
    });

    lightboxClose.addEventListener("click", closeLightbox);

    lightbox.addEventListener("click", (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && lightbox.classList.contains("open")) {
            closeLightbox();
        }
    });
}

document.querySelectorAll(".product-row[data-href]").forEach((row) => {
    row.addEventListener("click", (e) => {
        if (e.target.closest("a, button, form")) return;
        window.location.href = row.dataset.href;
    });
});