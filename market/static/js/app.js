// CampusMarket — скрипты интерфейса
(function () {
  var pendingForm = null;

  // Создание или получение модального окна подтверждения
  function getConfirmDialog() {
    var dlg = document.getElementById("confirm-modal");
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.id = "confirm-modal";
      dlg.className = "modal";
      dlg.innerHTML =
        '<div class="modal-box" style="max-width: 440px;">' +
        '<div class="modal-head"><h2 style="font-size: 18px;" id="confirm-title">Подтверждение</h2>' +
        '<button type="button" class="modal-x" data-confirm-cancel aria-label="Закрыть">×</button></div>' +
        '<p id="confirm-message" style="margin: 12px 0 20px; font-size: 14px; line-height: 1.5; color: var(--text);"></p>' +
        '<div class="modal-actions">' +
        '<button type="button" class="btn btn-outline btn-sm" data-confirm-cancel>Отмена</button>' +
        '<button type="button" class="btn btn-primary btn-sm" id="confirm-ok">Подтвердить</button></div></div>';
      document.body.appendChild(dlg);
    }
    bindConfirmEvents(dlg);
    return dlg;
  }

  function bindConfirmEvents(dlg) {
    if (dlg._hasEvents) return;
    dlg._hasEvents = true;

    var okBtn = dlg.querySelector("#confirm-ok");
    if (okBtn) {
      okBtn.addEventListener("click", function () {
        if (pendingForm) {
          pendingForm._confirmed = true;
          dlg.close();
          if (typeof pendingForm.requestSubmit === "function") {
            pendingForm.requestSubmit();
          } else {
            pendingForm.submit();
          }
          pendingForm = null;
        }
      });
    }

    dlg.querySelectorAll("[data-confirm-cancel]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        pendingForm = null;
        dlg.close();
      });
    });

    dlg.addEventListener("click", function (e) {
      if (e.target === dlg) {
        pendingForm = null;
        dlg.close();
      }
    });

    dlg.addEventListener("cancel", function () {
      pendingForm = null;
    });
  }

  // 1. Перехват подтверждений действий: НИКАКИХ браузерных window.confirm
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var question = form.getAttribute("data-confirm");
    var submitter = e.submitter;
    if (submitter && submitter.getAttribute("data-confirm")) {
      question = submitter.getAttribute("data-confirm");
    }

    if (question) {
      if (form._confirmed) {
        delete form._confirmed;
        // Если это удаление сообщения - удаляем в фоне через AJAX
        if (form.classList.contains("msg-del-form")) {
          e.preventDefault();
          var bubble = form.closest(".bubble");
          fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" }
          }).then(function () {
            if (bubble) bubble.remove();
          });
        }
        return;
      }
      e.preventDefault();
      pendingForm = form;
      var dlg = getConfirmDialog();
      var msg = dlg.querySelector("#confirm-message");
      if (msg) msg.textContent = question;
      if (typeof dlg.showModal === "function") {
        dlg.showModal();
      }
      return;
    }

    // Блокировка кнопки при отправке формы
    if (form.hasAttribute("data-loading")) {
      var btns = form.querySelectorAll("button[type=submit], button:not([type])");
      setTimeout(function () {
        btns.forEach(function (b) { b.disabled = true; b.classList.add("is-loading"); });
      }, 0);
    }
  });

  // 2. Отправка сообщений по нажатию Enter (Shift+Enter для новой строки)
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      var textarea = e.target;
      if (textarea && textarea.tagName === "TEXTAREA" && textarea.closest(".chat-form")) {
        e.preventDefault();
        var form = textarea.closest(".chat-form");
        if (textarea.value.trim().length > 0) {
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
          } else {
            form.submit();
          }
        }
      }
    }
  });

  // 3. Универсальное открытие/закрытие модальных окон
  document.addEventListener("click", function (e) {
    var openBtn = e.target.closest("[data-modal-open]");
    if (openBtn) {
      var targetSel = openBtn.getAttribute("data-modal-open");
      var modal = document.querySelector(targetSel);
      if (modal && typeof modal.showModal === "function") {
        modal.showModal();
      }
    }
    var closeBtn = e.target.closest("[data-modal-close]");
    if (closeBtn) {
      var dlg = closeBtn.closest("dialog.modal");
      if (dlg && typeof dlg.close === "function") {
        dlg.close();
      }
    }
  });

  // Закрытие любого <dialog class="modal"> по клику на фон
  document.querySelectorAll("dialog.modal").forEach(function (dlg) {
    dlg.addEventListener("click", function (e) {
      if (e.target === dlg) {
        dlg.close();
      }
    });
  });

  // 4. Глазок для паролей
  function initPasswordToggles() {
    document.querySelectorAll("input[type=password]").forEach(function (inp) {
      if (inp.closest(".password-wrap")) return;
      var wrap = document.createElement("div");
      wrap.className = "password-wrap";
      inp.parentNode.insertBefore(wrap, inp);
      wrap.appendChild(inp);

      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "password-toggle";
      toggle.setAttribute("aria-label", "Показать пароль");
      toggle.innerHTML = '<svg class="i"><use href="#i-eye"/></svg>';
      wrap.appendChild(toggle);

      toggle.addEventListener("click", function () {
        var isPass = inp.type === "password";
        inp.type = isPass ? "text" : "password";
        toggle.setAttribute("aria-label", isPass ? "Скрыть пароль" : "Показать пароль");
        toggle.innerHTML = isPass
          ? '<svg class="i"><use href="#i-eye-off"/></svg>'
          : '<svg class="i"><use href="#i-eye"/></svg>';
      });
    });
  }

  // 5. Фоновая отправка сообщений в обычном чате заявки
  function initRegularChat() {
    var regularChatForm = document.querySelector(".chat-form");
    var chatBox = document.getElementById("chat");
    var isBotForm = document.getElementById("bot-form");

    if (regularChatForm && chatBox && !isBotForm) {
      regularChatForm.addEventListener("submit", function (e) {
        var textInput = regularChatForm.querySelector("textarea[name=text]");
        if (!textInput) return;
        var textVal = textInput.value.trim();
        if (!textVal) return;

        e.preventDefault();

        var timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        var bubble = document.createElement("div");
        bubble.className = "bubble me";
        var content = document.createElement("div");
        content.className = "bubble-content";
        var p = document.createElement("p");
        p.className = "prewrap";
        p.textContent = textVal;
        content.appendChild(p);
        bubble.appendChild(content);

        var timeEl = document.createElement("time");
        timeEl.textContent = timeStr;
        bubble.appendChild(timeEl);
        chatBox.appendChild(bubble);
        chatBox.scrollTop = chatBox.scrollHeight;

        var fd = new FormData(regularChatForm);
        textInput.value = "";

        fetch(regularChatForm.action || window.location.href, {
          method: "POST",
          body: fd,
          headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json();
        })
        .then(function (data) {
          if (data.created_at) timeEl.textContent = data.created_at;
          if (data.id) {
            bubble.id = "msg-" + data.id;
            var formDel = document.createElement("form");
            formDel.method = "post";
            formDel.action = "/messages/" + data.id + "/delete/";
            formDel.className = "msg-del-form";
            formDel.setAttribute("data-confirm", "Удалить это сообщение?");
            var csrfInput = regularChatForm.querySelector("input[name=csrfmiddlewaretoken]");
            if (csrfInput) {
              var csrfClone = csrfInput.cloneNode(true);
              formDel.appendChild(csrfClone);
            }
            formDel.innerHTML += '<button type="submit" class="msg-del-btn" aria-label="Удалить сообщение" title="Удалить сообщение">×</button>';
            content.appendChild(formDel);
          }
        })
        .catch(function () {});
      });
    }
  }

  // 6. Инициализация остальных элементов после загрузки DOM
  document.addEventListener("DOMContentLoaded", function () {
    var confirmDlg = document.getElementById("confirm-modal");
    if (confirmDlg) bindConfirmEvents(confirmDlg);
    initPasswordToggles();
    initRegularChat();

    // Галерея на странице объявления
    document.querySelectorAll(".thumb").forEach(function (t) {
      t.addEventListener("click", function () {
        var main = document.getElementById("gallery-main");
        if (main) main.src = t.getAttribute("data-src");
        document.querySelectorAll(".thumb").forEach(function (x) { x.classList.remove("on"); });
        t.classList.add("on");
      });
    });

    // Панель фильтров на мобильных
    document.querySelectorAll("[data-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var el = document.querySelector(b.getAttribute("data-toggle"));
        if (el) el.classList.toggle("open");
      });
    });

    // Автоприменение сортировки
    document.querySelectorAll("[data-autosubmit]").forEach(function (s) {
      s.addEventListener("change", function () { s.form.submit(); });
    });

    // Прокрутка чата
    var chatBox = document.getElementById("chat");
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

    // Исчезающие уведомления
    setTimeout(function () {
      document.querySelectorAll(".toast-success").forEach(function (t) { t.style.display = "none"; });
    }, 6000);
  });
})();
