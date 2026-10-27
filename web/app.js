"use strict";

const buttons = document.querySelectorAll("[data-mode]");
const status = document.getElementById("status");

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    status.textContent = `Wybrano tryb ${button.dataset.mode}. To tylko podgląd lokalny.`;
  });
});
