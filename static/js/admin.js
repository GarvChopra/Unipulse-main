/* UNIFIX Admin portal — shell interactions only.
   Progressive enhancement: every link/form works without this file. */
(() => {
  "use strict";
  const body = document.body;
  const $ = (id) => document.getElementById(id);

  /* ---- mobile navigation drawer ---- */
  const side = $("axSide");
  const burger = $("axBurger");
  const OPEN = "ax-drawer-open";

  const setDrawer = (open) => {
    body.classList.toggle(OPEN, open);
    if (burger) burger.setAttribute("aria-expanded", String(open));
  };
  const drawerOpen = () => body.classList.contains(OPEN);

  if (burger) burger.addEventListener("click", () => setDrawer(!drawerOpen()));
  document.querySelectorAll("[data-drawer-close]").forEach((el) =>
    el.addEventListener("click", () => setDrawer(false))
  );
  // close after choosing a destination on small screens
  if (side) {
    side.querySelectorAll("a[href]").forEach((a) =>
      a.addEventListener("click", () => {
        if (window.matchMedia("(max-width: 1080px)").matches) setDrawer(false);
      })
    );
  }

  /* ---- notification popover ---- */
  const bell = $("axBell");
  const notif = $("axNotif");
  const setNotif = (open) => {
    if (!notif) return;
    notif.hidden = !open;
    if (bell) bell.setAttribute("aria-expanded", String(open));
  };
  if (bell && notif) {
    bell.addEventListener("click", (e) => {
      e.stopPropagation();
      setNotif(notif.hidden);
    });
    document.addEventListener("click", (e) => {
      if (!notif.hidden && !notif.contains(e.target) && e.target !== bell) setNotif(false);
    });
  }

  /* ---- global keyboard ---- */
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setDrawer(false);
      setNotif(false);
    }
  });

  /* ---- reset drawer state when crossing the desktop breakpoint ---- */
  const mq = window.matchMedia("(min-width: 1081px)");
  const onChange = () => { if (mq.matches) setDrawer(false); };
  mq.addEventListener ? mq.addEventListener("change", onChange) : mq.addListener(onChange);
})();
