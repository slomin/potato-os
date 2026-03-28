"use strict";

let _styleLink = null;
let _chatModule = null;

export async function init(container, shellApi) {
  // 1. Fetch and inject chat HTML fragment
  const res = await fetch("/app/chat/assets/chat.html");
  container.innerHTML = await res.text();

  // 2. Load chat CSS
  _styleLink = document.createElement("link");
  _styleLink.rel = "stylesheet";
  _styleLink.href = "/app/chat/assets/chat.css";
  document.head.appendChild(_styleLink);

  // 3. Import and init chat
  _chatModule = await import("/app/chat/assets/chat.js");
  _chatModule.init(shellApi);
}

export function destroy() {
  if (_styleLink) {
    _styleLink.remove();
    _styleLink = null;
  }
  _chatModule = null;
}
