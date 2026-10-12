/* ETS2 Photorealism storefront front-end.
   Talks only to our own server; the server owns all amounts and verifies every
   payment with PayPal before a key is issued. */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  const state = { config: null, paypalLoaded: false, products: {} };

  // ---------- helpers ----------
  const validEmail = (v) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test((v || "").trim());
  const emailVal = () => ($("#buyer-email")?.value || "").trim();

  let toastTimer;
  function toast(msg, kind = "") {
    const t = $("#toast");
    t.textContent = msg;
    t.className = "toast " + kind;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 4200);
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  // ---------- ToS gate ----------
  const TOS_KEY = "ets2_tos_agreed";
  const tosAgreed = () => localStorage.getItem(TOS_KEY) === "1";

  // ---------- product cards ----------
  function renderProducts() {
    const host = $("#products");
    host.innerHTML = "";
    state.config.products.forEach((p) => {
      const isPremium = p.key === "premium";
      const card = document.createElement("article");
      card.className = "product" + (isPremium ? " is-premium" : "");
      card.innerHTML = `
        <span class="badge">${p.badge}</span>
        <h3>${p.name.replace("ETS2 Photorealism - ", "")}</h3>
        <p class="blurb">${p.blurb}</p>
        <div class="price">
          <span class="now">$${p.total}</span>
          <span class="cur">${p.currency}</span>
          <span class="tax">incl. ${Math.round(p.tax_rate * 100)}% tax</span>
        </div>
        <div class="pay-slot" data-slot="${p.key}">
          <span class="pay-note">Loading checkout…</span>
        </div>
        <p class="pay-note">One-time key · instant download · keep forever</p>`;
      host.appendChild(card);
      state.products[p.key] = p;
    });
  }

  function lockPaySlots(showLocked) {
    $$(".pay-slot").forEach((slot) => {
      if (showLocked) {
        slot.innerHTML = `<span class="pay-locked">✓ Agree to the Terms above to unlock checkout</span>`;
      }
    });
  }

  // ---------- PayPal ----------
  function loadPayPal() {
    if (state.paypalLoaded) return Promise.resolve();
    state.paypalLoaded = true;
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src =
        `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(state.config.paypal_client_id)}` +
        `&currency=${state.config.currency}&intent=capture`;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load PayPal."));
      document.head.appendChild(s);
    });
  }

  function setSlot(key, html) {
    const slot = $(`.pay-slot[data-slot="${key}"]`);
    if (slot) slot.innerHTML = html;
  }

  async function mountPayButtons() {
    if (!window.paypal) return;
    Object.values(state.products).forEach((p) => {
      setSlot(p.key, `<div id="pp-${p.key}"></div>`);
      window.paypal
        .Buttons({
          style: { layout: "vertical", shape: "rect", color: "gold", height: 44, label: "pay" },
          onClick: (_data, actions) => {
            if (!tosAgreed()) {
              toast("Please agree to the Terms of Service first.", "err");
              return actions.reject();
            }
            if (!validEmail(emailVal())) {
              setEmailError("Enter a valid email — your key is sent there.");
              toast("Enter a valid email address first.", "err");
              return actions.reject();
            }
            return actions.resolve();
          },
          createOrder: async () => {
            const d = await postJSON("/api/create-order", { tier: p.key, email: emailVal() });
            return d.orderID;
          },
          onApprove: async (data) => {
            try {
              const d = await postJSON("/api/capture-order", { orderID: data.orderID });
              if (d.already_paid) {
                toast("This order was already completed. Check your email for the key.", "ok");
                return;
              }
              showConfirmation(d);
            } catch (e) {
              toast(e.message, "err");
            }
          },
          onError: (err) => toast(String(err || "PayPal error."), "err"),
          onCancel: () => toast("Checkout cancelled — you were not charged."),
        })
        .render(`#pp-${p.key}`)
        .catch(() => setSlot(p.key, `<span class="pay-locked">Checkout unavailable right now.</span>`));
    });
  }

  async function initPay() {
    if (!state.config.paypal_client_id) {
      lockPaySlots(false);
      $$(".pay-slot").forEach(
        (s) => (s.innerHTML = `<span class="pay-locked">Payments not configured yet.</span>`)
      );
      return;
    }
    if (!tosAgreed()) { lockPaySlots(true); return; }
    try {
      await loadPayPal();
      await mountPayButtons();
    } catch (e) {
      toast(e.message, "err");
    }
  }

  // ---------- confirmation modal ----------
  function showConfirmation(d) {
    $("#confirm-key").textContent = d.key;
    $("#confirm-email").textContent = (d.emails || []).join(", ") || "your email";
    const note = $("#confirm-email-note");
    note.textContent = d.email_sent
      ? "Email sent. Copy the key above as a backup."
      : "⚠ We couldn't send the email — copy this key now, it's the only copy.";
    note.className = "hint" + (d.email_sent ? "" : " err");
    $("#confirm-modal").hidden = false;
    $("#copy-key").onclick = async () => {
      try { await navigator.clipboard.writeText(d.key); toast("Key copied.", "ok"); }
      catch { toast("Copy failed — select the key manually.", "err"); }
    };
  }

  // ---------- redeem ----------
  function formatKeyInput(el) {
    const raw = el.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 20);
    el.value = (raw.match(/.{1,5}/g) || []).join("-");
  }

  async function redeem() {
    const key = $("#key-input").value.trim();
    const msg = $("#redeem-msg");
    msg.className = "redeem-msg";
    if (!key) { msg.textContent = "Enter your key."; msg.classList.add("err"); return; }
    $("#redeem-btn").disabled = true;
    try {
      const d = await postJSON("/api/redeem", { key });
      const label = d.tier === "premium" ? "Premium" : "Standard";
      msg.textContent = `Unlocked ${label} — starting your download…`;
      msg.classList.add("ok");
      // manual link in case the auto-redirect is blocked
      const a = document.createElement("a");
      a.href = d.download_url; a.textContent = "Click here if the download didn't start.";
      a.style.display = "block"; a.style.marginTop = "10px";
      msg.appendChild(a);
      setTimeout(() => (window.location.href = d.download_url), 700);
    } catch (e) {
      msg.textContent = e.message;
      msg.classList.add("err");
    } finally {
      $("#redeem-btn").disabled = false;
    }
  }

  // ---------- email field ----------
  function setEmailError(text) {
    const hint = $("#email-hint");
    if (text) { hint.textContent = text; hint.classList.add("err"); }
    else { hint.textContent = "Use an email you can check right now."; hint.classList.remove("err"); }
  }

  // ---------- boot ----------
  async function init() {
    $("#year").textContent = new Date().getFullYear();

    const check = $("#tos-check");
    check.checked = tosAgreed();
    check.addEventListener("change", () => {
      localStorage.setItem(TOS_KEY, check.checked ? "1" : "0");
      if (check.checked) initPay();
      else lockPaySlots(true);
    });

    $("#buyer-email")?.addEventListener("input", () => setEmailError(null));
    $("#key-input")?.addEventListener("input", (e) => formatKeyInput(e.target));
    $("#key-input")?.addEventListener("keydown", (e) => { if (e.key === "Enter") redeem(); });
    $("#redeem-btn")?.addEventListener("click", redeem);
    $$("[data-close]").forEach((b) =>
      b.addEventListener("click", () => ($("#confirm-modal").hidden = true))
    );
    $("#confirm-modal")?.addEventListener("click", (e) => {
      if (e.target.id === "confirm-modal") e.target.hidden = true;
    });

    try {
      const res = await fetch("/api/config");
      state.config = await res.json();
      renderProducts();
      await initPay();
    } catch (e) {
      toast("Could not load store config.", "err");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
