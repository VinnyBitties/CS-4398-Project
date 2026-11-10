"use strict";
(() => {
  const $ = id => document.getElementById(id);
  if (!$("retro-loading")) {
    const bar = document.createElement("div");
    bar.id = "retro-loading"; bar.className = "retro-loading"; bar.hidden = true;
    const label = document.createElement("span"); label.textContent = "Rendering page…";
    const blocks = document.createElement("span"); blocks.className = "retro-loading-blocks";
    blocks.setAttribute("aria-hidden", "true"); blocks.textContent = "▰ ▰ ▰ ▰ ▰";
    const skip = document.createElement("button"); skip.id = "skip-render";
    skip.type = "button"; skip.textContent = "Skip animation";
    bar.append(label, blocks, skip); document.body.append(bar);
  }
  // Cosmetic, stepped painting only: requests, stage updates and error handling run normally.
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const reveals = new Map();
  let skipRendering = false;
  function finishReveal(group) {
    const reveal = reveals.get(group);
    if (reveal) {
      clearTimeout(reveal.timer);
      for (const node of reveal.nodes) {
        node.classList.remove("retro-reveal");
        node.style.removeProperty("--render-delay");
      }
      reveals.delete(group);
    }
    $("retro-loading").hidden = reveals.size === 0;
  }
  function finishAllReveals() {
    for (const group of [...reveals.keys()]) finishReveal(group);
  }
  function revealInChunks(group, nodes) {
    finishReveal(group);
    if (skipRendering || reducedMotion.matches || document.hidden) return;
    nodes = nodes.filter(node => node && !node.hidden);
    if (!nodes.length) return;
    nodes.forEach((node, index) => {
      node.style.setProperty("--render-delay", `${index * 230}ms`);
      node.classList.add("retro-reveal");
    });
    reveals.set(group, { nodes, timer: setTimeout(() => finishReveal(group), (nodes.length - 1) * 230 + 650) });
    $("retro-loading").hidden = false;
  }
  $("skip-render").addEventListener("click", () => {
    skipRendering = true;
    finishAllReveals();
    (document.getElementById("scan-dashboard") || document.querySelector("main"))?.focus({ preventScroll: true });
  });
  reducedMotion.addEventListener("change", () => { if (reducedMotion.matches) finishAllReveals(); });
  window.RetroLoading = { revealInChunks, finishReveal, finishAllReveals };
  window.addEventListener("pagehide", finishAllReveals);
  document.addEventListener("visibilitychange", () => { if (document.hidden) finishAllReveals(); });
  revealInChunks("page", [...document.querySelectorAll("[data-retro-render]")]);
})();
