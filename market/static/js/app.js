// Небольшие улучшения интерфейса. Без JS сайт тоже работает (обычные формы).
(function () {
  // Подтверждение опасных действий: <form data-confirm="Текст вопроса">
  // и <button data-confirm="..."> внутри формы.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var question = form.getAttribute("data-confirm");
    var submitter = e.submitter;
    if (submitter && submitter.getAttribute("data-confirm")) question = submitter.getAttribute("data-confirm");
    if (question && !window.confirm(question)) { e.preventDefault(); return; }
    // Состояние загрузки: блокируем кнопку, чтобы не отправить форму дважды
    if (form.hasAttribute("data-loading") || question) {
      var btns = form.querySelectorAll("button[type=submit], button:not([type])");
      setTimeout(function () {
        btns.forEach(function (b) { b.disabled = true; b.classList.add("is-loading"); });
      }, 0);
    }
  });

  // Галерея на странице объявления
  document.querySelectorAll(".thumb").forEach(function (t) {
    t.addEventListener("click", function () {
      var main = document.getElementById("gallery-main");
      if (main) main.src = t.getAttribute("data-src");
      document.querySelectorAll(".thumb").forEach(function (x) { x.classList.remove("on"); });
      t.classList.add("on");
    });
  });

  // Панель фильтров на телефоне
  document.querySelectorAll("[data-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = document.querySelector(b.getAttribute("data-toggle"));
      if (el) el.classList.toggle("open");
    });
  });

  // Сортировка применяется сразу
  document.querySelectorAll("[data-autosubmit]").forEach(function (s) {
    s.addEventListener("change", function () { s.form.submit(); });
  });

  // Чат: прокрутка к последнему сообщению
  var chat = document.getElementById("chat");
  if (chat) chat.scrollTop = chat.scrollHeight;

    // Окно предпросмотра при загрузке фотографий
  var input = document.querySelector("[data-upload-modal]");
  var dlg = document.getElementById("upload-modal");
  if (input && dlg && typeof dlg.showModal === "function" && window.DataTransfer) {
    var grid = document.getElementById("upload-grid");
    var counter = document.getElementById("upload-counter");
    var errorBox = document.getElementById("upload-error");
    var okBtn = document.getElementById("upload-ok");
    var summary = document.getElementById("upload-summary");
    var MAX = parseInt(input.getAttribute("data-max"), 10) || 5;
    var MAX_SIZE = 5 * 1024 * 1024;
    var TYPES = ["image/jpeg", "image/png", "image/webp"];
    var defaultSummary = summary ? summary.textContent : "";
    var files = [];
    var urls = [];

    function slots() {
      var existing = parseInt(input.getAttribute("data-existing"), 10) || 0;
      var removed = document.querySelectorAll("input[name=delete_images]:checked").length;
      return Math.max(0, MAX - (existing - removed));
    }

    function problem(f) {
      if (TYPES.indexOf(f.type) === -1) return "допустимы только JPG, PNG и WebP";
      if (f.size > MAX_SIZE) return "файл больше 5 МБ";
      return "";
    }

    function render() {
      urls.forEach(function (u) { URL.revokeObjectURL(u); });
      urls = [];
      grid.innerHTML = "";
      var errors = [];
      files.forEach(function (f, index) {
        var bad = problem(f);
        if (bad) errors.push("«" + f.name + "»: " + bad + ".");
        var item = document.createElement("div");
        item.className = "preview-item" + (bad ? " bad" : "");
        var frame = document.createElement("div");
        frame.className = "preview-frame";
        var img = document.createElement("img");
        var url = URL.createObjectURL(f);
        urls.push(url);
        img.src = url;
        img.alt = f.name;
        frame.appendChild(img);
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "preview-remove";
        rm.setAttribute("aria-label", "Убрать фото");
        rm.textContent = "×";
        rm.addEventListener("click", function () { files.splice(index, 1); render(); });
        frame.appendChild(rm);
        var name = document.createElement("span");
        name.className = "preview-name";
        name.textContent = f.name;
        item.appendChild(frame);
        item.appendChild(name);
        grid.appendChild(item);
      });
      var free = slots();
      if (files.length > free) errors.push("Можно добавить не более " + free + " фото (максимум " + MAX + " на объявление).");
      counter.textContent = "Выбрано: " + files.length + ". Свободных мест: " + free + ".";
      errorBox.hidden = errors.length === 0;
      errorBox.textContent = errors.join(" ");
      okBtn.disabled = errors.length > 0 || files.length === 0;
    }

    function applySelection() {
      var dt = new DataTransfer();
      files.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
      if (summary) summary.textContent = files.length ? "Выбрано фото: " + files.length : defaultSummary;
    }

    function cancel() {
      files = [];
      input.value = "";
      if (summary) summary.textContent = defaultSummary;
      if (dlg.open) dlg.close();
    }

    input.addEventListener("change", function () {
      files = Array.prototype.slice.call(input.files);
      if (!files.length) { cancel(); return; }
      render();
      dlg.showModal();
    });
    okBtn.addEventListener("click", function () {
      if (okBtn.disabled) return;
      applySelection();
      dlg.close();
    });
    dlg.querySelectorAll("[data-modal-cancel]").forEach(function (b) { b.addEventListener("click", cancel); });
    dlg.addEventListener("cancel", function (e) { e.preventDefault(); cancel(); });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) cancel(); });
  }

  // Исчезающие уведомления
  setTimeout(function () {
    document.querySelectorAll(".toast-success").forEach(function (t) { t.style.display = "none"; });
  }, 6000);
})();
