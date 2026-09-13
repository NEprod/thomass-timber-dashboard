document.addEventListener("DOMContentLoaded", () => {
  const copyButton = document.getElementById("copy_cutlist");
  const display = document.getElementById("cutlist_display");

  if (copyButton && display) {
    copyButton.addEventListener("click", () => {
      const text = display.textContent.trim();

      if (!text) {
        alert("Nothing to copy.");
        return;
      }

      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();

      try {
        const successful = document.execCommand("copy");
        alert(successful ? "Cutlist copied to clipboard!" : "Copy failed.");
      } catch (err) {
        alert("Copy not supported in this browser.");
        console.error(err);
      }

      document.body.removeChild(textarea);
    });
  }
});