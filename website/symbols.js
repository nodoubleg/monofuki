"use strict";

(() => {
  function searchMatcher(value) {
    const query = value.trim().toLowerCase().replace(/^nf-/, "");
    const code = /^(?:u\+|0x)([0-9a-f]*)$/.exec(query);
    if (code) {
      const prefix = code[1].replace(/^0+(?=.)/, "");
      return (codepoint) => codepoint.toLowerCase().replace(/^0+(?=.)/, "").startsWith(prefix);
    }
    const words = query.replace(/[-_]/g, " ");
    return (codepoint, name) => `${name} ${codepoint}`.toLowerCase().replace(/[-_]/g, " ").includes(words);
  }

  const controls = document.querySelector(".symbol-controls");
  if (!controls) return;
  const search = document.querySelector("#symbol-search");
  const block = document.querySelector("#symbol-block");
  const donor = document.querySelector("#symbol-donor");
  const cards = Array.from(document.querySelectorAll(".symbol-card"));
  const groups = Array.from(document.querySelectorAll(".symbol-group"));
  const count = document.querySelector("#symbol-count");
  const copyStatus = document.querySelector("#copy-status");
  let statusTimer;
  controls.hidden = false;

  function filter() {
    const matches = searchMatcher(search.value);
    let shown = 0;
    cards.forEach((card) => {
      card.hidden = !(
        matches(card.dataset.codepoint, card.dataset.name) &&
        (block.value === "all" || card.dataset.block === block.value) &&
        (donor.value === "all" || card.dataset.donor === donor.value)
      );
      if (!card.hidden) shown += 1;
    });
    groups.forEach((group) => {
      const visible = group.querySelectorAll(".symbol-card:not([hidden])").length;
      const total = group.querySelectorAll(".symbol-card").length;
      group.hidden = visible === 0;
      group.querySelector(".group-count").textContent = visible === total ? total : `${visible} / ${total}`;
    });
    count.textContent = `Showing ${shown} of ${cards.length} symbols`;
    document.querySelector("#symbol-empty").hidden = shown !== 0;
  }
  search.addEventListener("input", filter);
  block.addEventListener("change", filter);
  donor.addEventListener("change", filter);
  document.querySelector("#symbol-reset").addEventListener("click", () => {
    search.value = "";
    block.value = donor.value = "all";
    history.replaceState(null, "", location.pathname + location.search + "#catalogue");
    filter();
    search.focus();
  });

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(String.fromCodePoint(parseInt(button.dataset.copy, 16)));
        copyStatus.textContent = `Copied U+${button.dataset.copy}`;
      } catch (_) {
        copyStatus.textContent = "Clipboard unavailable. Select the glyph to copy it.";
      }
      clearTimeout(statusTimer);
      statusTimer = setTimeout(() => { copyStatus.textContent = ""; }, 4000);
    });
  });

  function showLinkedGlyph() {
    const match = /^#u-([0-9a-f]+)$/i.exec(location.hash);
    if (!match || !document.getElementById(`u-${match[1].toLowerCase()}`)) return;
    document.querySelector("#catalogue").open = true;
    search.value = `U+${match[1].toUpperCase()}`;
    block.value = donor.value = "all";
    filter();
    document.getElementById(`u-${match[1].toLowerCase()}`).scrollIntoView({ block: "center" });
  }
  function openLinkedPanel() {
    const id = location.hash.slice(1);
    const target = document.getElementById(id);
    if (target && target.matches("details.catalog-panel")) target.open = true;
  }
  window.addEventListener("hashchange", openLinkedPanel);
  openLinkedPanel();
  window.addEventListener("hashchange", showLinkedGlyph);
  filter();
  showLinkedGlyph();

  const iconSearch = document.querySelector("#icon-search");
  if (iconSearch) {
    document.querySelector(".icon-search-label").hidden = false;
    const icons = Array.from(document.querySelectorAll(".nerd-icon"));
    function filterIcons() {
      const query = iconSearch.value.trim();
      const matches = searchMatcher(query);
      let shown = 0;
      icons.forEach((icon) => {
        icon.hidden = !matches(icon.dataset.codepoint, icon.dataset.iconSearch);
        if (!icon.hidden) shown += 1;
      });
      document.querySelectorAll(".icon-group").forEach((group) => {
        const visible = group.querySelectorAll(".nerd-icon:not([hidden])").length;
        const total = group.querySelectorAll(".nerd-icon").length;
        group.hidden = visible === 0;
        group.querySelector("summary span").textContent = visible === total ? total : `${visible} / ${total}`;
        if (query) group.open = visible !== 0;
        else group.open = false;
      });
      document.querySelector("#icon-count").textContent = `Showing ${shown} of ${icons.length} Nerd Font glyphs`;
      document.querySelector("#icon-empty").hidden = shown !== 0;
    }
    iconSearch.addEventListener("input", filterIcons);
    filterIcons();
  }
  const fallbackVariant = document.querySelector("#fallback-variant");
  if (fallbackVariant) {
    document.querySelector(".fallback-controls").hidden = false;
    const fallbackSearch = document.querySelector("#fallback-search");
    const previews = Array.from(document.querySelectorAll(".fallback-card"));
    function filterFallback() {
      const matches = searchMatcher(fallbackSearch.value);
      let shown = 0;
      previews.forEach((preview) => {
        preview.hidden = preview.dataset.variant !== fallbackVariant.value || !matches(preview.dataset.codepoint, preview.dataset.fallbackSearch);
        if (!preview.hidden) shown += 1;
      });
      document.querySelector("#fallback-count").textContent = `Showing ${shown} characters absent from ${fallbackVariant.value === "regular" ? "Monofuki" : "Monofuki Nerd Font"}`;
      document.querySelector("#fallback-empty").hidden = shown !== 0;
    }
    fallbackVariant.addEventListener("change", filterFallback);
    fallbackSearch.addEventListener("input", filterFallback);
    filterFallback();
  }
})();
