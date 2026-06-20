const DEFAULT_DASH_URL = "https://your-dashboard.up.railway.app";
(async function () {
  const { dashUrl, password } = await chrome.storage.local.get(["dashUrl", "password"]);
  document.getElementById("dashUrl").value = dashUrl || DEFAULT_DASH_URL;
  if (password) document.getElementById("password").value = password;
  document.getElementById("save").onclick = async () => {
    await chrome.storage.local.set({
      dashUrl: document.getElementById("dashUrl").value.trim(),
      password: document.getElementById("password").value.trim(),
    });
    document.getElementById("ok").textContent = "Saved ✓";
    setTimeout(() => (document.getElementById("ok").textContent = ""), 1500);
  };
})();
