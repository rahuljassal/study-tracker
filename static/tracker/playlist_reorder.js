(() => {
  const list = document.querySelector("[data-reorder-url]");
  if (!list) return;

  const status = document.querySelector("#reorder-status");
  let draggedRow = null;

  const saveOrder = async () => {
    const csrfToken = list.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    const videoIds = Array.from(list.querySelectorAll(".video-row"))
      .map((row) => Number(row.dataset.videoId));

    status.textContent = "Saving playlist order…";
    try {
      const response = await fetch(list.dataset.reorderUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ video_ids: videoIds }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "Could not save playlist order.");
      }
      window.location.reload();
    } catch (error) {
      window.alert(error.message || "Could not save playlist order. Please try again.");
      window.location.reload();
    }
  };

  list.addEventListener("dragstart", (event) => {
    const handle = event.target.closest(".drag-handle");
    if (!handle) return;
    draggedRow = handle.closest(".video-row");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", draggedRow.dataset.videoId);
    requestAnimationFrame(() => draggedRow?.classList.add("is-dragging"));
  });

  list.addEventListener("dragover", (event) => {
    const targetRow = event.target.closest(".video-row");
    if (!draggedRow || !targetRow || targetRow === draggedRow) return;
    event.preventDefault();
    const bounds = targetRow.getBoundingClientRect();
    const insertAfter = event.clientY > bounds.top + bounds.height / 2;
    list.querySelectorAll(".drop-target").forEach((row) => {
      row.classList.remove("drop-target");
    });
    targetRow.classList.add("drop-target");
    list.insertBefore(
      draggedRow,
      insertAfter ? targetRow.nextSibling : targetRow,
    );
  });

  list.addEventListener("drop", (event) => {
    if (!draggedRow) return;
    event.preventDefault();
    list.querySelectorAll(".drop-target").forEach((row) => {
      row.classList.remove("drop-target");
    });
    draggedRow.classList.remove("is-dragging");
    draggedRow = null;
    void saveOrder();
  });

  list.addEventListener("dragend", () => {
    draggedRow?.classList.remove("is-dragging");
    draggedRow = null;
    list.querySelectorAll(".drop-target").forEach((row) => {
      row.classList.remove("drop-target");
    });
  });
})();
