(() => {
  const toc = document.querySelector("#page-contents");
  document.querySelectorAll("article h2[id]").forEach((heading) => {
    const link = document.createElement("a");
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent;
    toc.append(link);
  });
  if (toc.children.length) document.querySelector(".contents").hidden = false;

  // Deep links to a criterion/source/protocol must reveal its folded content.
  function revealAnchor() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    const details = target.closest("details");
    if (details) {
      details.open = true;
      requestAnimationFrame(() => details.scrollIntoView({ block: "start" }));
    }
  }
  window.addEventListener("hashchange", revealAnchor);
  revealAnchor();
})();
